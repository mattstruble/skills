# GPU-Driven Rendering

Covers indirect dispatch and draw, multidraw indirect (MDI), GPU-driven culling pipelines, draw-argument barriers, and render passes with explicit load/store ops. Read this when implementing a GPU-driven scene, issuing indirect commands, or structuring render pass transitions.

Source: Sebastian Aaltonen's "No Graphics API" blog post; `leotmp/no_gfx_api` Odin implementation: https://github.com/leotmp/no_gfx_api

---

## What "GPU-Driven" Means

In a traditional CPU-driven renderer, the CPU iterates over visible objects and issues one draw call per object. At scale (thousands of objects), CPU submission becomes the bottleneck.

In a GPU-driven renderer:
- A compute shader runs on the GPU, reads bounding volumes and camera data, and writes surviving draw arguments into a GPU buffer.
- The CPU issues **one indirect draw** that consumes whatever the compute shader produced.
- The GPU generates its own workload — the CPU's role shrinks to: bind root data, dispatch culling compute, issue indirect draw.

| Approach | CPU work per frame | Draw calls | Scales to |
|---|---|---|---|
| CPU-driven | Cull + submit per object | 1 per visible object | ~10K objects |
| GPU-driven (indirect) | Bind + dispatch + 1 draw | 1 indirect draw | Millions of objects |
| GPU-driven (mesh shaders) | Bind + dispatch | 0 draw calls | Millions of meshlets |

Mesh shaders extend this further by bypassing the vertex+index buffer model entirely. See `mesh-shaders.md` (planned reference).

---

## Indirect Dispatch

Indirect dispatch lets a compute shader determine the thread group count for a subsequent compute dispatch. The dispatch arguments live in a GPU buffer, not a CPU parameter.

```
// CPU side: bind compute data and fire dispatch
// 'arguments' is a GPU pointer to a Dispatch_Indirect_Command struct
gpuDispatchIndirect(commandBuffer, data.gpu, arguments.gpu);

// Dispatch_Indirect_Command layout:
// { num_groups_x: u32, num_groups_y: u32, num_groups_z: u32 }
```

Odin API:
```
cmd_dispatch_indirect: proc(cmd_buf: Command_Buffer,
    compute_data: gpuptr,
    arguments: ptr_t(Dispatch_Indirect_Command))

Dispatch_Indirect_Command :: struct {
    num_groups_x: u32,
    num_groups_y: u32,
    num_groups_z: u32,
}
```

**Use case**: A first-pass compute shader counts surviving objects and writes the group count for a second-pass compute. The second pass processes exactly as many groups as needed — no CPU readback required.

---

## Indirect Draw

Indirect draw moves draw arguments (vertex count, instance count, offsets) into a GPU buffer. A compute shader can write these arguments before the draw.

```
// Both root data AND draw arguments are GPU pointers.
// A compute shader can write dataVertex, dataPixel, and arguments
// before this call — no CPU involvement.
gpuDrawIndexedInstancedIndirect(commandBuffer,
    dataVertex.gpu,    // GPU pointer to vertex shader root data
    dataPixel.gpu,     // GPU pointer to pixel shader root data
    indices.gpu,       // GPU pointer to index buffer
    arguments.gpu);    // GPU pointer to DrawIndexedInstancedArgs
```

**Key difference from Vulkan/DX12/Metal**: In standard APIs, root data (uniforms, descriptor sets) is always CPU-provided. Here, a GPU compute shader can write both the draw arguments **and** the per-draw root data — the CPU never touches per-draw state.

Odin API:
```
cmd_draw_indexed_indirect_raw: proc(cmd_buf: Command_Buffer,
    vertex_data, fragment_data, indices: gpuptr,
    index_format: Index_Format,
    indirect_arguments: gpuptr)
```

---

## Indirect Multidraw (MDI)

A single multidraw command issues N draws from arrays of arguments. The GPU draw count (`drawCount.gpu`) is a pointer to a `u32` that the culling compute shader wrote — the CPU never knows how many draws survived.

```
// Draw N surviving objects with one command:
// - dataVertex.gpu: base of an array of DataVertex structs, stride bytes apart
// - dataPixel.gpu:  base of an array of DataPixel structs, stride bytes apart
// - arguments.gpu:  base of an array of DrawIndexedInstancedArgs
// - drawCount.gpu:  pointer to a u32 written by the culling compute shader
// - maxDrawCount:   capacity of the arguments array (API clamps GPU count to this)
gpuDrawIndexedInstancedIndirectMulti(
    commandBuffer,
    dataVertex.gpu, sizeof(DataVertex),
    dataPixel.gpu,  sizeof(DataPixel),
    arguments.gpu,
    drawCount.gpu,
    maxDrawCount);  // must equal allocated capacity of arguments array
```

**Stride = 0**: Broadcast the same root data to all N draws. Useful when all draws share the same shader bindings but differ only in draw arguments (e.g., same material, different meshes).

**`maxDrawCount`**: Always set to the allocated capacity of the argument buffer. The API clamps the GPU-written count to this value, preventing the command processor from reading past the buffer end. Setting it to `UINT32_MAX` or omitting it is unsafe.

Odin API:
```
cmd_draw_indexed_indirect_multi_raw: proc(cmd_buf: Command_Buffer,
    vertex_data, fragment_data, indices: gpuptr,
    index_format: Index_Format,
    indirect_arguments: gpuptr,
    stride: u32,
    draw_count: gpuptr)
```

### Per-Draw Root Arguments

In standard APIs, per-draw data (object transform, material index) is passed via push constants or a draw ID that indexes into a storage buffer. In the "no graphics API" model, `dataVertex.gpu` and `dataPixel.gpu` are arrays — each draw reads its own slice at `base + drawIndex * stride`. The compute shader packs these arrays during culling.

| Mechanism | How per-draw data flows | API |
|---|---|---|
| `gl_DrawID` / `SV_StartInstanceLocation` | Scalar draw index; shader indexes into a storage buffer | Vulkan, DX12 SM6.8 |
| Push constant per draw | 32-bit root constant in command signature | DX12 ExecuteIndirect |
| Strided root data arrays | GPU pointer + stride; each draw reads its own struct | "No graphics API" / custom |

---

## Draw-Argument Barrier

**Critical**: whenever a compute shader writes draw or dispatch arguments, a barrier with `HAZARD_DRAW_ARGUMENTS` must be placed before the indirect call. Without it, the command processor prefetches stale data from the argument buffer.

```
// 1. Dispatch culling compute — writes argumentBuffer and drawCount
//    Ceiling division: (numObjects + 63) / 64 ensures all objects are processed.
//    If numObjects can be 0, clamp to at least 1 (DX12 treats 0-count dispatch as UB).
gpuDispatch(commandBuffer, cullingData.gpu, uvec3((numObjects + 63) / 64, 1, 1));

// 2. Barrier: stall command processor prefetch, invalidate argument cache.
//    Destination is STAGE_DRAW_INDIRECT (the command processor argument fetch stage),
//    not STAGE_COMPUTE. Using STAGE_COMPUTE as destination only synchronizes
//    compute→compute work and does NOT guarantee the command processor sees the writes.
gpuBarrier(commandBuffer, STAGE_COMPUTE, STAGE_DRAW_INDIRECT, HAZARD_DRAW_ARGUMENTS);

// 3. Indirect multidraw — reads the arguments the compute just wrote
gpuDrawIndexedInstancedIndirectMulti(commandBuffer, ..., argumentBuffer.gpu, drawCount.gpu);
```

| Without barrier | With barrier |
|---|---|
| Command processor may prefetch argument buffer before compute finishes writing | Prefetch stalled until compute writes are visible |
| Draws use stale or uninitialized arguments | Draws use the GPU-written arguments |
| Silent corruption — no validation error | Correct behavior |

The destination stage must be `STAGE_DRAW_INDIRECT` (Vulkan: `VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT`; DX12: `D3D12_BARRIER_SYNC_EXECUTE_INDIRECT`). If the producer is a raster pass writing to a UAV, use `(STAGE_RASTER_COLOR_OUT, STAGE_DRAW_INDIRECT)` or equivalent.

**Indirect dispatch arguments require the same barrier**: if a compute shader writes a `Dispatch_Indirect_Command`, place a `HAZARD_DRAW_ARGUMENTS` barrier before `gpuDispatchIndirect`. The two-phase culling pattern (first compute writes group count for second compute) requires this barrier between the two dispatches.

---

## GPU-Driven Culling Pipeline

The canonical GPU-driven scene rendering loop:

```
Frame setup (CPU, once):
  - Upload BoundingVolumes[] (one per object; updated by CPU or GPU skinning)
  - Upload AllDrawArguments[] (pre-filled at load time; per-object draw params)
  - Upload camera frustum planes as uniforms
  - Pre-allocate drawArguments[] and perDrawData[] for maxObjects entries

Step 1 — Culling compute:
  Thread group size: (64, 1, 1)
  One thread per object.
  Dispatch: (numObjects + 63) / 64 groups (ceiling division).

Step 2 — Draw-argument barrier (STAGE_COMPUTE → STAGE_DRAW_INDIRECT)

Step 3 — One indirect multidraw covers the entire scene
```

Culling compute pseudocode:
```
// pseudocode — not valid HLSL; CullData bound as ConstantBuffer in real code
[numthreads(64, 1, 1)]
void CullObjects(uint objectIdx : SV_DispatchThreadID, CullData* data) {
    if (objectIdx >= data->objectCount) return;

    BoundingVolume bv = data->boundingVolumes[objectIdx];

    // Frustum test (and optionally occlusion / HZB test)
    if (!IsVisible(bv, data->frustumPlanes)) return;

    // Atomically claim a slot in the output arrays
    uint slot;
    InterlockedAdd(data->drawCount[0], 1, slot);

    // Guard: drop this draw if output buffer is full.
    // Without this, slot >= maxObjects is an out-of-bounds GPU write.
    if (slot >= data->maxObjects) return;

    // Pack surviving draw into output arrays
    data->drawArguments[slot] = data->allDrawArguments[objectIdx];
    data->perDrawData[slot]   = data->allPerDrawData[objectIdx];
}
```

After the barrier, one call renders the entire scene:
```
// ponytail: vertex and pixel root data use the same struct here;
// use separate arrays if your vertex and pixel root data differ.
gpuDrawIndexedInstancedIndirectMulti(cmd,
    perDrawData.gpu, sizeof(PerDrawData),
    perDrawData.gpu, sizeof(PerDrawData),
    drawArguments.gpu,
    drawCount.gpu,
    maxObjects);
```

### Two-Phase Culling (HZB Occlusion)

For occlusion culling, the pipeline extends to two phases:

| Phase | What it does |
|---|---|
| **Phase 1** | Frustum cull only; render surviving objects; build Hierarchical Z-Buffer (HZB) from depth |
| **Phase 2** | Test phase-1-rejected objects against HZB; render newly visible objects |

This is out of scope here; the single-phase frustum-cull pattern above covers the common case.

---

## Render Passes

A render pass groups draw calls that share the same set of render targets. Explicit load/store ops replace automatic clears and resolves.

```
// G-buffer pass
gpuBeginRenderPass(commandBuffer, {
    .depthTarget  = {.texture = depth,      .loadOp = CLEAR,     .storeOp = DONT_CARE, .clearValue = 1.0f},
    .colorTargets = {
        {.texture = gBufAlbedo, .loadOp = DONT_CARE, .storeOp = STORE},
        {.texture = gBufNormal, .loadOp = DONT_CARE, .storeOp = STORE},
    }
});
// ... draw calls ...
gpuEndRenderPass(commandBuffer);

// Barrier: G-buffer outputs → lighting pass reads as textures
gpuBarrier(commandBuffer,
    STAGE_RASTER_COLOR_OUT | STAGE_RASTER_DEPTH_OUT,
    STAGE_PIXEL_SHADER);   // or STAGE_COMPUTE if lighting is compute

// Lighting pass
gpuBeginRenderPass(commandBuffer, {
    .colorTargets = { {.texture = hdrColor, .loadOp = DONT_CARE, .storeOp = STORE} }
});
// ...
gpuEndRenderPass(commandBuffer);
```

Odin API:
```
cmd_begin_render_pass: proc(cmd_buf: Command_Buffer, desc: Render_Pass_Desc)
cmd_end_render_pass:   proc(cmd_buf: Command_Buffer)

Render_Pass_Desc :: struct {
    render_area_offset: [2]i32,
    render_area_size:   [2]u32,  // {0, 0} = full texture dimensions at BeginRenderPass time.
                                 // If the texture has zero extent (e.g., minimized window),
                                 // skip the render pass entirely — zero-extent is UB on Vulkan
                                 // and crashes on some Metal drivers.
    color_attachments:  []Render_Attachment,
    depth_attachment:   Maybe(Render_Attachment),
    stencil_attachment: Maybe(Render_Attachment),
}

Render_Attachment :: struct {
    texture:         Texture,
    load_op:         Load_Op,   // Clear, Load, Dont_Care
    store_op:        Store_Op,  // Store, Dont_Care, Resolve, Resolve_And_Store
    clear_color:     [4]f32,
    resolve_texture: Texture,
}
```

### Load/Store Op Reference

| Op | Category | When to use |
|---|---|---|
| `CLEAR` | Load | Initialize to a known value. Avoids a separate clear call. On TBDR, free if tile is fresh. |
| `LOAD` | Load | Continue rendering onto existing content (UI overlay, multi-pass accumulation). |
| `DONT_CARE` | Load | Content will be fully overwritten this pass (G-buffer fully covered). Allows TBDR to skip tile load. |
| `STORE` | Store | Written values needed after the pass (render target used as texture in next pass). |
| `DONT_CARE` | Store | Content not needed after pass (depth after deferred shading). Allows TBDR to skip tile store. |
| `RESOLVE` | Store | MSAA resolve into a non-MSAA texture on pass end. |
| `RESOLVE_AND_STORE` | Store | Resolve MSAA and also keep the MSAA surface. |

### TBDR (Mobile) Notes

Tile-Based Deferred Renderers (Mali, Apple GPU, Adreno) process tiles entirely on-chip before writing to VRAM. Load/store ops directly control whether tiles touch VRAM:

| Load op | Store op | VRAM traffic | Use case |
|---|---|---|---|
| `DONT_CARE` | `DONT_CARE` | None — tile stays on-chip | Intermediate G-buffer targets |
| `DONT_CARE` | `STORE` | Write only | G-buffer final output |
| `CLEAR` | `DONT_CARE` | None (tile clear + render + discard) | Depth-only shadow pass |
| `LOAD` | `STORE` | Read + write | Multi-pass accumulation |
| `LOAD` | `DONT_CARE` | Read only | Read-modify-discard |

`LOAD` requires a tile fetch from VRAM — expensive on mobile if tiles aren't reused. Prefer `DONT_CARE` load whenever the pass fully overwrites the attachment.

### No Auto-Barriers at Pass Boundaries

Render passes do **not** insert automatic barriers between passes. The user is responsible for placing barriers between passes that have data dependencies.

**Why**: Auto-barriers prevent overlapping render passes that write disjoint targets. Two passes with no shared resources (e.g., shadow map depth prepass and main view depth prepass) can run concurrently on hardware that supports it — but only if no barrier is inserted between them. The Claybook (GDC 2018) Xbox One / PS4 optimizations exploited exactly this: render target overlap via precise user-placed barriers.

**Rule**: Place a barrier between pass A and pass B if and only if pass B reads or writes a resource that pass A wrote.

---

## Mesh Shaders Cross-Reference

Mesh shaders are the GPU-driven geometry path that replaces the vertex+index buffer model entirely:
- Thread groups generate **meshlets** (compact vertex + index data) on-chip.
- Enables per-meshlet culling, LOD selection, and procedural geometry — all on GPU.
- No index buffer, no vertex buffer — the mesh shader writes its own output vertices.

Use mesh shaders when: GPU-driven geometry is needed and target hardware is NVIDIA Turing / AMD RDNA2 or newer.

Full coverage is deferred to a planned `mesh-shaders` reference. The indirect draw pattern above is the fallback for hardware without mesh shader support.

---

## Common GPU-Driven Rendering Bugs

| Symptom | Cause | Fix |
|---|---|---|
| Indirect draw renders garbage geometry or zero objects | Missing draw-argument barrier | Add `gpuBarrier(..., STAGE_DRAW_INDIRECT, HAZARD_DRAW_ARGUMENTS)` between compute and indirect draw |
| Draw count is always 0 | `InterlockedAdd` target not zeroed before culling dispatch | Clear `drawCount` buffer to 0 each frame before culling; add a UAV/storage barrier between the clear and the culling dispatch |
| All objects drawn (culling has no effect) | Culling compute writes to wrong buffer slot, or `drawCount` not connected to multidraw | Verify buffer pointers and stride in multidraw call |
| More objects visible than expected; GPU memory corruption | `slot >= maxObjects` not guarded in culling shader | Add `if (slot >= data->maxObjects) return;` after `InterlockedAdd` |
| Indirect multidraw issues draws past argument buffer end | `maxDrawCount` not set or set to `UINT32_MAX` | Pass `maxDrawCount = bufferCapacity` to the indirect multidraw call |
| G-buffer has garbage pixels when scene is empty or partially culled | `loadOp = DONT_CARE` on G-buffer attachments when not all pixels are guaranteed written | Use `loadOp = CLEAR` for G-buffer attachments, or ensure a full-screen clear draw runs first |
| Render pass attachment has garbage on TBDR | `loadOp = DONT_CARE` on an attachment that wasn't fully overwritten | Use `loadOp = CLEAR` or ensure full coverage |
| Depth buffer visible in next pass as stale data | `storeOp = DONT_CARE` on depth, then next pass reads it | Use `storeOp = STORE` if depth is needed downstream |
| Two passes corrupt each other's render targets | Missing barrier between passes | Add barrier with correct stage flags between the two passes |
| Indirect dispatch launches wrong thread count | Dispatch argument buffer not initialized, or wrong byte offset | Verify `Dispatch_Indirect_Command` layout and buffer alignment; ensure buffer is initialized to safe values before first frame |

---

## API Sidebar

### Indirect Draw / Dispatch

| Concept | Vulkan | DX12 | Metal |
|---|---|---|---|
| Indirect draw | `vkCmdDrawIndexedIndirect` | `ExecuteIndirect` with `D3D12_INDIRECT_ARGUMENT_TYPE_DRAW_INDEXED` | `drawIndexedPrimitives(indirectBuffer:indirectBufferOffset:)` |
| Indirect dispatch | `vkCmdDispatchIndirect` | `ExecuteIndirect` with `D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH` | `dispatchThreadgroups(indirectBuffer:indirectBufferOffset:threadsPerThreadgroup:)` |
| Multidraw with GPU count | `vkCmdDrawIndexedIndirectCount` (Vulkan 1.2 / `VK_KHR_draw_indirect_count`) | `ExecuteIndirect` with count buffer (DX12 1.1+) | `MTLIndirectCommandBuffer` with encoded draw count |
| GPU device address for args | `VK_EXT_device_generated_commands` (Vulkan 1.4 core: `vkCmdExecuteGeneratedCommandsEXT`). Standard `vkCmdDrawIndexedIndirect` uses `VkBuffer` + offset, not a raw device address. | Root descriptor (GPU VA) in command signature | N/A — Metal uses buffer + offset |
| Per-draw data | `gl_DrawID` indexes into storage buffer | `D3D12_INDIRECT_ARGUMENT_TYPE_INCREMENTING_CONSTANT` (DX12 1.1) or `SV_StartInstanceLocation` (SM6.8) | `[[draw_index]]` in vertex shader |

### DX12 ExecuteIndirect Tiers

| Tier | What's added | Notes |
|---|---|---|
| **Tier 1** (original) | Pre-defined command signature; `DRAW_INDEXED` + optional 32-bit root constant per draw | Moderate hardware requirements; draw ID via root constant |
| **Tier 1.1** (2024) | `D3D12_INDIRECT_ARGUMENT_TYPE_INCREMENTING_CONSTANT` — auto-increments a root constant per draw | Maps to `SV_StartInstanceLocation` in SM6.8; fast-path on some command processors |

### Render Passes

| Concept | Vulkan | DX12 | Metal |
|---|---|---|---|
| Begin render pass | `vkCmdBeginRendering` (dynamic rendering, Vulkan 1.3 core) | `BeginRenderPass(rtDescs, dsDesc, flags)` on `ID3D12GraphicsCommandList4`; requires `D3D12_RENDER_PASS_TIER_0+` from `D3D12_FEATURE_D3D12_OPTIONS5`. Or legacy `OMSetRenderTargets`. | `renderCommandEncoder(descriptor:)` with `MTLRenderPassDescriptor` |
| End render pass | `vkCmdEndRendering` | `EndRenderPass` | `endEncoding` |
| Load op | `VkAttachmentLoadOp`: `LOAD`, `CLEAR`, `DONT_CARE` | `D3D12_RENDER_PASS_BEGINNING_ACCESS_TYPE`: `PRESERVE`, `CLEAR`, `DISCARD` | `MTLLoadAction`: `.load`, `.clear`, `.dontCare` |
| Store op | `VkAttachmentStoreOp`: `STORE`, `DONT_CARE` | `D3D12_RENDER_PASS_ENDING_ACCESS_TYPE`: `PRESERVE`, `DISCARD`, `RESOLVE` | `MTLStoreAction`: `.store`, `.dontCare`, `.multisampleResolve` |
| No auto-barriers | Manual `vkCmdPipelineBarrier2` / `vkCmdPipelineBarrier` between passes | Manual `ResourceBarrier` between passes | Manual `textureBarrier` / `memoryBarrier` between encoders |
| MSAA resolve | `RESOLVE` store op + `resolveImageLayout` | `D3D12_RENDER_PASS_ENDING_ACCESS_TYPE_RESOLVE` | `.multisampleResolve` or `.storeAndMultisampleResolve` |
