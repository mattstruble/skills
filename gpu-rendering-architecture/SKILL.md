---
name: gpu-rendering-architecture
summary: Modern GPU programming model: bindless resources, GPU-driven rendering, synchronization
type: reference
description: "You MUST consult this skill when reasoning about how modern GPUs are *driven* — bindless resources and descriptor heaps, 64-bit GPU pointers / buffer-device-address, GPU memory type selection (CPU-mapped vs GPU-private), GPU-driven and indirect/multidraw rendering, struct-based shader data model, PSO/state management and the PSO-permutation problem, modern stage-based barriers and timeline-semaphore synchronization. Engine-agnostic, grounded in Vulkan 1.3+ / DX12 SM6.6 / Metal 3+. NOT for software-rasterizer math (see game-rendering). NOT for engine/GDSL shader authoring (see godot-shader). NOT for GPU perf profiling or bottleneck diagnosis (see game-performance)."
---

# GPU Rendering Architecture

Engine-agnostic reference for the modern GPU programming model: how data reaches shaders, how resources are bound, how state is managed, and how synchronization works. Grounded in Vulkan 1.3+, DX12 SM6.6, and Metal 3+. Synthesized from Sebastian Aaltonen's *No Graphics API* blog series and the [`leotmp/no_gfx_api`](https://github.com/leotmp/no_gfx_api) Odin implementation.

**Relationship to other skills**: This skill covers *how the GPU is driven* — the data model, binding model, state management, and synchronization. For software-rasterizer math (coordinate spaces, barycentric coordinates, projection), see `game-rendering`. For engine/GDSL shader authoring in Godot 4.x, see `godot-shader`. For diagnosing GPU bottlenecks and frame-rate problems, see `game-performance`.

---

## Architecture Overview

The modern GPU programming model replaces per-draw API calls with a single root-pointer per dispatch/draw. The CPU writes structs into persistently-mapped GPU memory; the GPU reads them directly.

```
CPU (host)                              GPU (device)
─────────────────────────────────────────────────────────────────────
Frame arena (MEMORY_DEFAULT)
  ┌──────────────────────────────┐
  │ SceneData {                  │──── root pointer ────►  Vertex shader
  │   float4x4  viewProj         │                          reads via
  │   const Vertex*  verts       │──── GPU pointer ──────►  data->verts[id]
  │   const uint32*  indices     │──── GPU pointer ──────►  data->indices[id]
  │   uint32    textureBase      │──── heap index ───────►  textureHeap[base+0]
  │   uint32    drawCount        │
  │ }                            │
  └──────────────────────────────┘

Descriptor heap (MEMORY_DEFAULT)
  ┌────────────────────────────────────────────────────────────────┐
  │ slot 0 │ slot 1 │ slot 2 │ ... │ slot N │  (each = 256 bits)  │
  └────────────────────────────────────────────────────────────────┘
         ▲                                    ▲
    textureBase                          textureBase+N
    (color tex)                          (PBR tex)

GPU-private memory (MEMORY_GPU)
  ┌──────────────────────────────┐
  │ Vertex buffer (Morton-swizzled, DCC-compressed)               │
  │ Textures (Morton-swizzled, DCC-compressed)                    │
  └──────────────────────────────┘
         ▲
    Upload path: staging (MEMORY_DEFAULT) → copy cmd → GPU-private
```

**The data model in one sentence**: one `const Data*` root pointer per dispatch/draw; the struct may contain GPU pointers to other data — no vertex buffer objects, no uniform buffer objects, no descriptor sets.

---

## Decision Tables

### Memory Type Selection

| Need | Memory type | Why |
|------|------------|-----|
| Per-frame uniforms, draw args, descriptors | CPU-mapped (`MEMORY_DEFAULT`) | CPU writes directly; no copy needed; persistently mapped |
| Textures (sampled), large vertex/index data | GPU-private (`MEMORY_GPU`) | Enables DCC compression, Morton swizzle; better GPU bandwidth |
| GPU output to CPU (screenshots, readback) | Readback (`MEMORY_READBACK`) | CPU-cached; coherent after fence wait |

**Rule**: `MEMORY_DEFAULT` is almost always correct for per-frame data. Only use `MEMORY_GPU` when you need the GPU's compression hardware (textures, large persistent buffers).

### Descriptor / Binding Approach

| Approach | When | Trade-off |
|---------|------|---------|
| 32-bit heap index | All modern GPUs (Vulkan, DX12, AMD/ARM Metal) | 4 bytes; supports contiguous ranges (`base+0`, `base+1`, `base+2`); requires `NonUniformResourceIndex` for non-uniform access |
| 64-bit texture handle (Metal 3+) | Metal only | 8 bytes; no range concept; driver-managed heap; no annotation needed for non-uniform access |
| Embedded sampler | Fixed sampler params (linear clamp, nearest) | Zero heap slots; baked at pipeline creation; no dynamic anisotropy |
| Root pointer + GPU VA | Buffer data (not textures) | 8 bytes; full pointer arithmetic; no `NonUniformResourceIndex` needed |

### Barrier Selection

| Scenario | Barrier call |
|----------|-------------|
| Compute writes → compute reads (standard) | `barrier(COMPUTE, COMPUTE)` |
| Compute writes descriptors → shader samples | `barrier(COMPUTE, COMPUTE, HAZARD_DESCRIPTORS)` |
| Compute writes draw args → indirect draw | `barrier(COMPUTE, DRAW_INDIRECT, HAZARD_DRAW_ARGUMENTS)` |
| Rasterizer output → sample in next pass | `barrier(RASTER_COLOR_OUT, PIXEL_SHADER)` |
| Depth read → depth write (same attachment, reusing depth buffer) | `barrier(PIXEL_SHADER, RASTER_DEPTH_OUT, HAZARD_DEPTH_STENCIL)` |
| Transfer (copy/upload) → compute/shader | `barrier(TRANSFER, ALL)` |
| Transfer uploads texture → shader samples | `barrier(TRANSFER, ALL, HAZARD_DESCRIPTORS)` |

**Rule**: start with no hazard flags. Add `HAZARD_DRAW_ARGUMENTS` when writing indirect args, `HAZARD_DESCRIPTORS` when updating bindless tables, `HAZARD_DEPTH_STENCIL` when reusing a depth attachment (depth read → depth write — flushes HiZ cache).

### PSO State: Bake vs. Dynamic

| State | Action | Reason |
|-------|--------|--------|
| Shader IR | Always bake | IS the microcode |
| Render target formats, MSAA, topology | Always bake | Affects microcode generation |
| Alpha-to-coverage, dual-source blend | Always bake | Affects pixel shader register allocation |
| Depth-stencil | Separate state object | Pure command packet; no microcode rebuild |
| Blend state (desktop) | Separate state object OR dynamic | Command packet on desktop; no rebuild |
| Blend state (mobile TBDR) | Embed in PSO | Driver appends blend to PS microcode on Mali/Adreno/Apple |
| Cull mode, viewport, scissor | Dynamic (Vulkan 1.3+) | Command packet only |
| Vertex layout | Eliminate via programmable vertex fetch | No baked state; shader reads `data->verts[vertexId]` directly |

### CPU-Driven vs. GPU-Driven Rendering

| Approach | CPU work per frame | Draw calls | Scales to |
|---|---|---|---|
| CPU-driven | Cull + submit per object | 1 per visible object | ~10K objects |
| GPU-driven (indirect draw) | Bind + dispatch + 1 indirect draw | 1 | Millions of objects |
| GPU-driven (mesh shaders) | Bind + dispatch | 0 draw calls | Millions of meshlets |

---

## Symptoms → Cause

| Symptom | Cause | Fix |
|---------|-------|-----|
| Shader compilation stutter / 100 GB PSO caches | Too much state baked in PSOs | Move depth-stencil/blend/cull to dynamic state; use shader objects (`VK_EXT_shader_object`) |
| Texture appears as wrong content / GPU crash on texture sample | Missing `HAZARD_DESCRIPTORS` barrier after writing descriptor heap | Add `barrier(COMPUTE, COMPUTE, HAZARD_DESCRIPTORS)` between descriptor write and sample |
| Indirect draw reads stale arguments / GPU hang | Missing `HAZARD_DRAW_ARGUMENTS` barrier after culling compute | Add `barrier(COMPUTE, DRAW_INDIRECT, HAZARD_DRAW_ARGUMENTS)` |
| Non-uniform texture access produces wrong pixels / driver crash | Missing `NonUniformResourceIndex` on heap index | Annotate non-uniform heap index with `NonUniformResourceIndex()` (HLSL) or `nonuniformEXT()` (GLSL) |
| GPU reads stale render target after render pass | Barrier placed after wrong stage | Use `STAGE_RASTER_COLOR_OUT` (not `STAGE_PIXEL_SHADER`) as producer stage |
| Descriptor write lost between frames | Heap slot written then freed before GPU reads it | Heap slots must remain valid for all frames-in-flight; background streaming threads must not overwrite a slot while any in-flight command buffer references it — double-buffer the slot or wait for the referencing fence |
| Upload data garbage / GPU reads zeros | Staging buffer freed before GPU copy command executes | Hold staging lifetime until fence signals GPU completion |
| Frame memory corruption | `arena_free_all` before `semaphore_wait` | Wait on frame semaphore before freeing that frame's arena |
| Blend produces wrong result on mobile | Blend state not embedded in PSO | Mobile TBDR requires baked blend or framebuffer fetch |
| Indirect draw count always 0 | `drawCount` buffer not zeroed before culling dispatch | Clear `drawCount` to 0 each frame; add `barrier(TRANSFER, COMPUTE)` (or `barrier(COMPUTE, COMPUTE)` if clearing via compute) between the clear and the culling dispatch |
| GPU fault on texture sample | Texture allocated with wrong alignment | Query `gpuTextureSizeAlign(desc)` and use returned `.align` |
| Shader reads garbage after resource update | Descriptor table holds stale GPU pointer to freed allocation | Rebuild descriptor table entries when reallocating resources |

---

## API Feature Matrix

| Feature | Vulkan | DX12 | Metal |
|---------|--------|------|-------|
| 64-bit GPU pointers | `VK_KHR_buffer_device_address` (core 1.2) | Root descriptors (inline GPU VA in root sig) | `MTLBuffer.gpuAddress` (Metal 2+, macOS 10.14+) |
| Bindless textures | `VK_EXT_descriptor_buffer` (2023) | `ResourceDescriptorHeap[]` (SM6.6) | `gpuResourceID` + `MTLResidencySet` (Metal 3+, macOS 13+) |
| Dynamic rendering (no render pass objects) | `VK_KHR_dynamic_rendering` (core 1.3) | `BeginRenderPass` (available since Win10 SDK 1809; Tier 0/1/2 describes driver support quality) | Always (Metal uses `MTLRenderPassDescriptor` inline) |
| Extended dynamic state | `VK_EXT_extended_dynamic_state` v1/v2/v3 (partial core 1.3) | Limited (stencil ref, blend factor only) | Separate `MTLDepthStencilState` object |
| Shader objects (no PSO) | `VK_EXT_shader_object` (Roadmap 2024) | Not available | Not available |
| Timeline semaphores | `VK_KHR_timeline_semaphore` (core 1.2) | `ID3D12Fence` monotonic counter | `MTLSharedEvent` |
| Indirect multidraw with GPU count | `vkCmdDrawIndexedIndirectCount` (core 1.2) | `ExecuteIndirect` tier 1.1 (2023) | `MTLIndirectCommandBuffer` |
| Image layout transitions removal | `VK_KHR_unified_image_layouts` (2025, opt-in) | Not needed (DX12 resource states, no layout) | Not needed |
| Non-uniform texture indexing | `GL_EXT_nonuniform_qualifier` (`nonuniformEXT`) | `NonUniformResourceIndex()` (SM6.0+) | Native — no annotation needed |
| Specialization constants | `VkSpecializationInfo` | No direct equivalent; use `#define` + recompile | `MTLFunctionConstantValues` |

---

## Min-Spec Hardware

| GPU family | Minimum gen | Year | Notes |
|-----------|------------|------|-------|
| Nvidia | Turing (RTX 2000) | 2018 | Ray tracing, tensor cores, mesh shaders (VK_NV_mesh_shader only; VK_EXT_mesh_shader requires Ampere), full BDA, ReBAR (unofficial on Turing) |
| AMD | RDNA2 (RX 6000) | 2020 | Coherent L2$, ray tracing, Smart Access Memory (ReBAR); mesh shaders require RDNA3 (RX 7000, 2022) |
| Intel | Alchemist / Xe1 (Arc A-series) | 2022 | First Intel with SM6.6, mesh shaders, ray tracing, ReBAR |
| Apple | M1 / A14 | 2020 | `gpuAddress` available since Metal 2 (macOS 10.14+); `gpuResourceID` (bindless textures) + `MTLResidencySet` require Metal 3 (macOS 13, 2022); full UMA |
| ARM Mali | Mali-G710 | 2021 | Vulkan BDA, descriptor buffer, dynamic rendering; G715 (2022) adds ray tracing |
| Qualcomm | Adreno 650 | 2019 | Vulkan BDA, descriptor buffer; Adreno 740 (2022) adds ray tracing |

**TBDR note**: Apple Silicon Macs (M1/M2/M3), ARM Mali, and Qualcomm Adreno are Tile-Based Deferred Renderers even on desktop/laptop. Blend state must be baked into the PSO or use framebuffer fetch on these architectures.

---

## Key Invariants

**1. Bindless is the baseline.** A descriptor heap gives every shader access to every texture via a 32-bit index. No per-draw texture binding API. The heap is bound once per command buffer.

**2. GPU pointer + struct = the data model.** One `const Data*` root pointer per dispatch/draw. The struct may contain GPU pointers to other data — no vertex buffers, no uniform buffer objects, no descriptor sets. **Safety**: GPU virtual addresses carry no hardware bounds enforcement on most architectures — an out-of-bounds dereference reads or writes arbitrary GPU memory. Validate all offsets CPU-side before writing into root structs. Add explicit bounds checks in shaders when offsets are derived from GPU-written data.

**3. Three memory types.** CPU-mapped (default, persistently mapped), GPU-private (textures, large persistent data), Readback (for CPU reads of GPU output). Match to purpose.

**4. Stage mask + hazard flags = the barrier model.** No per-resource lists. Most barriers need no hazard flags. `HAZARD_DRAW_ARGUMENTS` after GPU writes indirect args; `HAZARD_DESCRIPTORS` after GPU writes descriptors.

**5. PSO permutation kills perf.** Minimize baked state; use dynamic state, shader objects, and static constants for permutation reduction.

**6. Transient command buffers.** Create, record, submit, done. No reuse. The driver uses a bump allocator; memory is reclaimed after GPU signals completion.

**7. Timeline semaphores.** One counter, monotonically increasing. `wait(N - FRAMES_IN_FLIGHT)` before touching frame N's resources. `arena_free_all` only after the semaphore wait.

**8. Write through `.cpu`; pass `.gpu` to GPU commands.** A `MEMORY_DEFAULT` allocation has two addresses. Never pass a `.cpu` pointer to a shader — it will fault or silently read garbage.

**9. Staging lifetime = GPU copy completion.** Keep staging allocations alive until the upload fence signals. Freeing the staging buffer before the copy engine finishes causes silent corruption.

**10. `NonUniformResourceIndex` on non-uniform heap indices.** Required in HLSL/GLSL when different lanes may sample different textures (deferred shading, ray tracing). Not needed for buffer pointer arithmetic.

---

## Worked Examples

### Example 1: Passing per-draw material data to shaders

**Query**: "How should I pass per-draw material data to shaders — push constants, uniform buffers, or something else?"

**Skill-guided response**:

Use the root-pointer model. Allocate a `Material` struct in the per-frame arena (CPU-mapped memory), store GPU pointers to textures and other arrays in it, pass its GPU address as the single root pointer.

```cpp
// Shared CPU/GPU header:
struct alignas(16) MaterialData {
    float4   baseColor;        // 16 bytes — preloaded into scalar regs
    float    roughness;        // 4 bytes
    float    metallic;         // 4 bytes
    uint32   textureBase;      // 4 bytes — heap index; color=base+0, normal=base+1, pbr=base+2
    uint32   _pad;             // 4 bytes — padding; struct is 40 bytes raw, rounds to 48 with alignas(16)
    const float4x4* transform; // 8 bytes — GPU pointer to transform buffer
    // SECURITY: const is not just a performance hint (scalar register path).
    // A writable GPU pointer in a root struct is an arbitrary GPU memory write primitive
    // if its value is ever derived from GPU-written data. Keep output pointers CPU-controlled.
};

// CPU side (per draw):
auto mat = frameArena.allocate<MaterialData>();
mat.cpu->baseColor    = {1.0f, 0.5f, 0.2f, 1.0f};
mat.cpu->roughness    = 0.4f;
mat.cpu->metallic     = 0.0f;
mat.cpu->textureBase  = material.heapBaseIndex;
mat.cpu->transform    = transformBuffer.gpu;

gpuDrawIndexed(cmd,
    mat.gpu,   // vertex shader root pointer
    mat.gpu,   // pixel shader root pointer (same struct here; pass separate ptr when stages differ)
    indices, count);
```

**Why not push constants**: push constants are for tiny hot data (< 32 bytes, e.g., a frame counter or matrix index). They don't scale to arbitrary-size per-draw data.

**Why not uniform buffers**: uniform buffers add descriptor overhead — a descriptor set entry per buffer, alignment requirements, and binding API calls. The root-pointer model eliminates all of this.

**Root pointer is the sweet spot**: one 8-byte GPU VA in the command stream; the driver preloads the struct's leading fields into scalar registers before the wave launches; pointer arithmetic handles any size.

---

### Example 2: GPU-driven culling writes garbage draw arguments

**Query**: "My GPU-driven culling compute shader writes draw arguments, then the indirect draw reads garbage. What's wrong?"

**Skill-guided response**:

Missing `HAZARD_DRAW_ARGUMENTS` barrier. The command processor prefetches indirect arguments before the compute shader's writes are visible. The barrier must target `STAGE_DRAW_INDIRECT` (not `STAGE_COMPUTE`) as the destination stage.

```cpp
// 1. Culling compute — writes argumentBuffer and drawCount
//    max(1u, ...) avoids zero-count dispatch (DX12 UB on zero thread groups)
gpuDispatch(cmd, cullingData.gpu, {max(1u, (numObjects + 63) / 64), 1, 1});

// 2. REQUIRED: stall command processor prefetch
//    dstStage must be DRAW_INDIRECT, not COMPUTE
gpuBarrier(cmd, STAGE_COMPUTE, STAGE_DRAW_INDIRECT, HAZARD_DRAW_ARGUMENTS);

// 3. Indirect multidraw — now reads the GPU-written arguments
gpuDrawIndexedIndirectMulti(cmd,
    perDrawData.gpu, sizeof(PerDrawData),
    perDrawData.gpu, sizeof(PerDrawData),
    argumentBuffer.gpu,
    drawCount.gpu,
    maxObjects);  // always set to buffer capacity — never UINT32_MAX
```

**Also check**:
- `drawCount` buffer zeroed before culling dispatch each frame (otherwise count accumulates); add `barrier(TRANSFER, COMPUTE)` between the clear and the culling dispatch
- `maxObjects` set to the actual buffer capacity (not `UINT32_MAX`) to prevent the command processor reading past the buffer end
- Culling shader guards `if (slot >= data->maxObjects) return;` after `InterlockedAdd` — this is a **security boundary**: without it, a GPU-written `slot` value can write draw arguments to arbitrary GPU memory addresses

---

## Relationship to Other Skills

**game-rendering** — Software-rasterizer math: coordinate spaces, perspective projection, barycentric coordinates, Z-buffer, backface culling. This skill covers *how the GPU is driven*; game-rendering covers *what the GPU computes*. When game-rendering mentions "GPU pipeline stages (vertex shaders, fragment shaders, rasterizer hardware)", it defers to Khronos — this skill fills that gap.

**godot-shader** — Engine/GDSL shader authoring in Godot 4.x: `.gdshader` files, GDSL syntax, visual effects, lighting models, post-processing. This skill covers the API-level programming model; godot-shader covers the shader language and engine integration. The concepts overlap (bindless textures, barriers) but the implementation is Godot-specific in godot-shader.

**game-performance** — Diagnosing and fixing GPU bottlenecks: profiling, fill-rate, bandwidth, CPU submission overhead. This skill explains how the pipeline is structured; game-performance explains how to measure and fix it when it's too slow. PSO permutation stutter is a design problem (this skill); measuring shader occupancy is a profiling problem (game-performance).

**odin-gamedev** — Odin/raylib glue patterns and the `leotmp/no_gfx_api` implementation. The reference files in this skill use Odin API examples from `no_gfx_api`. For Odin-specific patterns (type system, allocators, `rawptr` interop), see odin-gamedev.

---

## References

| File | Contents | Read when... |
|------|----------|--------------|
| `references/memory-model.md` | UMA/ReBAR topology, three memory types, upload pattern, arena allocators | Choosing memory type, debugging upload corruption |
| `references/data-binding.md` | GPU pointers, root arguments, shared headers, static constants, wide loads | Designing shader data layout, eliminating descriptor overhead |
| `references/bindless-textures.md` | Descriptor heap, 32-bit indices, non-uniform access, descriptor write flow | Setting up bindless textures, debugging wrong texture samples |
| `references/state-and-pipelines.md` | PSO explosion, dynamic state, shader objects, programmable vertex fetch | Reducing PSO permutations, choosing blend/depth-stencil strategy |
| `references/sync-and-barriers.md` | Stage-based barriers, hazard flags, split barriers, timeline semaphores | Writing correct sync, diagnosing GPU hang or stale read |
| `references/gpu-driven-rendering.md` | Indirect draw/dispatch, MDI, culling pipeline, render pass load/store | Setting up GPU-driven rendering, debugging indirect draw failures |

---

## Further Reading

- Sebastian Aaltonen, *No Graphics API* blog series: https://iolite-engine.com/blog_posts/no_graphics_api — the primary source for this skill; covers the full "no graphics API" programming model
- [`leotmp/no_gfx_api`](https://github.com/leotmp/no_gfx_api) — Odin implementation of the concepts in this skill
- [Vulkan 1.3 spec](https://registry.khronos.org/vulkan/specs/1.3/html/) — authoritative reference for `VK_KHR_synchronization2`, `VK_EXT_descriptor_buffer`, `VK_EXT_shader_object`
- [DX12 Agility SDK docs](https://devblogs.microsoft.com/directx/) — Enhanced Barriers, ExecuteIndirect tier 1.1, SM6.6 bindless
- [Metal Shading Language Specification](https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf) — `gpuAddress`, `gpuResourceID`, argument buffers (Metal 3+)
