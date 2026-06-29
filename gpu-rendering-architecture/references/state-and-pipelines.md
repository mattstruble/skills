# Pipeline State Management

Covers PSO/pipeline state objects: the permutation explosion, the immediate↔retained pendulum, what state must be baked vs. what can be dynamic, separate state objects, shader objects, and programmable vertex fetch. Read this when designing a rendering abstraction layer, choosing between PSO-based and shader-object-based pipelines, or debugging pipeline compilation stutter.

Source: Sebastian Aaltonen, *No Graphics API* blog series (rasterizer state and graphics shader bindings sections); `leotmp/no_gfx_api` Odin implementation.

---

## The PSO Permutation Explosion

A **Pipeline State Object (PSO)** in Vulkan 1.0 / DX12 bakes nearly all rasterizer state into one compiled object at creation time. The GPU driver compiles shader microcode at PSO creation — a process that can take hundreds of milliseconds per PSO.

### Scale of the Problem

| Metric | Real-world figure |
|--------|------------------|
| User local PSO cache size | **>100 GB** per user for large games |
| Cloud PSO cache servers | **Terabytes per GPU architecture/driver combination** (Valve, NVIDIA) |
| Single PSO compile time | 10–500 ms (driver-dependent) |
| Typical AAA game PSO count | Tens of thousands to hundreds of thousands |
| Stutter on first draw | Visible frame drops until PSO is compiled or loaded from cache |

### Root Cause

Only a small subset of state actually affects shader microcode. Vulkan 1.0 baked *everything* — including state that modern GPUs configure via command packets with no shader recompilation needed.

```
PSO creation → driver compiles shader microcode
             → microcode depends on: shader IR, RT formats, MSAA, topology
             → microcode does NOT depend on: depth-stencil, blend, cull, viewport
             → but Vulkan 1.0 baked all of it anyway (matched 2015 hardware model)
```

---

## What Must Be Baked vs. What Can Be Dynamic

| State | Must bake? | Why |
|-------|-----------|-----|
| Vertex + pixel shader IR | **Yes** | It IS the microcode |
| Primitive topology | **Yes** | Affects vertex shader launch dimensions; mesh shader dispatch |
| Render target formats | **Yes** | Affects pixel shader output register packing |
| MSAA sample count | **Yes** | Affects pixel shader launch granularity |
| Alpha-to-coverage | **Yes** | Affects pixel shader output coverage mask |
| `supportDualSourceBlending` | **Yes** | Affects pixel shader register allocation (exports two colors) |
| Depth-stencil state | **No** | Pure command packet on modern desktop HW |
| Blend state | **No** (desktop) / **Yes** (mobile TBDR) | Mobile driver appends blend to PS microcode |
| Viewport / scissor | **No** | Pure command packet |
| Cull mode | **No** | Pure command packet |
| Stencil reference value | **No** | Dynamic state since Vulkan 1.0 |
| Depth bias | **No** | Dynamic state since Vulkan 1.0 (`VK_DYNAMIC_STATE_DEPTH_BIAS` flag) |

**Mobile exception**: TBDR GPUs (ARM Mali, Qualcomm Adreno, Apple Silicon, PowerVR) execute blending inside the pixel shader on-chip. The driver appends blend instructions to the PS microcode — so blend state *does* affect microcode on mobile and must be baked or handled via framebuffer fetch. Note: Apple Silicon Macs (M1/M2/M3) are TBDR even on desktop/laptop — the same rule applies.

---

## The Immediate ↔ Retained Pendulum

| Era | API | State model | Problem |
|-----|-----|-------------|---------|
| OpenGL (1992–) | Fine-grained setters (`glDepthFunc`, `glBlendFunc`, …) | Immediate — set individual state before each draw | Driver overhead; driver must track and validate all state combinations |
| DX9 (2002) | State blocks | Semi-retained | Better batching, but driver still validated everything at draw time |
| DX11 (2009) | `ID3D11DepthStencilState`, `ID3D11BlendState` objects | Separate objects, set dynamically | Reduced validation; still driver-managed |
| DX12 (2015) / Vulkan 1.0 (2016) | Monolithic PSO — everything baked | Fully retained | PSO explosion; RHI abstraction mismatch with game engines |
| Vulkan 1.3 (2022) | `VK_EXT_extended_dynamic_state` (v1/v2/v3 device extensions, subset promoted to 1.3 core) | Hybrid — most state dynamic | Major permutation reduction; depth-stencil/cull/viewport now dynamic in core; blend/vertex-input via optional extensions |
| Metal (2014–) | Separate `MTLDepthStencilState`; blend in `MTLRenderPipelineDescriptor` | Partially separate | Reduces DS permutations; blend still baked |
| `VK_EXT_shader_object` (2023) | No PSO at all | Fully dynamic per command | Ideal for modern desktop; some mobile overhead |

**Pattern**: The industry over-corrected from OpenGL's per-draw state churn to Vulkan 1.0's everything-baked model, then walked it back with dynamic state extensions. The correct model for modern hardware is: bake only what affects microcode, set everything else dynamically.

---

## Separate Depth-Stencil State

Depth-stencil state is a command packet on modern hardware — no shader recompilation. Create a state object once, set it dynamically per draw.

```cpp
GpuDepthStencilDesc dsDesc = {
    .depthMode  = DEPTH_READ | DEPTH_WRITE,
    .depthTest  = OP_LESS_EQUAL,
    // defaults: no depth bias, stencil disabled, mask=0xff
};
GpuDepthStencilState dsState = gpuCreateDepthStencilState(dsDesc);

// Per draw — just sends a command packet, no PSO rebuild:
gpuSetDepthStencilState(commandBuffer, dsState);
```

**Odin equivalent** (`leotmp/no_gfx_api`):

```odin
Depth_State :: struct {
    mode:    Depth_Flags,  // Read, Write, or both
    compare: Compare_Op,   // Less, Equal, Less_Equal, Always, etc.
}

// Dynamic — command packet only:
cmd_set_depth_state(cmd_buf, Depth_State{
    mode    = .Read | .Write,
    compare = .Less_Equal,
})
```

---

## Blend State: Three Options

### Option 1 — Embedded in PSO (universal, including mobile)

Required for mobile TBDR. Blend instructions are appended to the pixel shader microcode by the driver.

```cpp
GpuRasterDesc rasterDesc = {
    .depthFormat  = FORMAT_D32_FLOAT,
    .colorTargets = { { .format = FORMAT_RGBA8_UNORM } },
    .blendState   = GpuBlendDesc {
        .colorOp         = BLEND_ADD,
        .srcColorFactor  = FACTOR_SRC_ALPHA,
        .dstColorFactor  = FACTOR_ONE_MINUS_SRC_ALPHA,
        .alphaOp         = BLEND_ADD,
        .srcAlphaFactor  = FACTOR_ONE,
        .dstAlphaFactor  = FACTOR_ZERO,
    },
};
GpuPipeline pipeline = gpuCreateGraphicsPipeline(vertIR, pixelIR, rasterDesc);
```

### Option 2 — Separate blend state object (desktop + some mobile; requires feature flag)

```cpp
GpuBlendState blendState = gpuCreateBlendState(blendDesc);
gpuSetBlendState(commandBuffer, blendState);  // one command packet; no PSO rebuild
```

**Odin equivalent**:

```odin
Blend_State :: struct {
    enable:           bool,
    color_op:         Blend_Op,
    src_color_factor: Blend_Factor,
    dst_color_factor: Blend_Factor,
    alpha_op:         Blend_Op,
    src_alpha_factor: Blend_Factor,
    dst_alpha_factor: Blend_Factor,
    color_write_mask: Color_Component_Flags,
}

cmd_set_blend_state(cmd_buf, Blend_State{
    enable           = true,
    color_op         = .Add,
    src_color_factor = .Src_Alpha,
    dst_color_factor = .One_Minus_Src_Alpha,
    alpha_op         = .Add,
    src_alpha_factor = .One,
    dst_alpha_factor = .Zero,
})
```

### Option 3 — Framebuffer fetch (mobile TBDR only)

On TBDR GPUs (Mali, Adreno, Apple, PowerVR), the current tile lives in on-chip scratchpad adjacent to the compute unit. The pixel shader can read the previous rasterized pixel at zero bandwidth cost. The driver appends blend instructions directly to the PS.

```glsl
// Pseudocode — actual API syntax differs per platform:
// Vulkan: VK_EXT_shader_tile_image uses tileImageEXT + colorAttachmentReadEXT()
// Metal:  [[color(0)]] input attribute on the fragment function
float4 dst = framebuffer_load();                          // reads current tile pixel — free on TBDR
float4 result = src.rgb * src.a + dst.rgb * (1.0 - src.a);
framebuffer_store(result);
```

**Capabilities unlocked by framebuffer fetch**:
- Custom blend formulas not expressible in fixed-function blend hardware
- Order-independent transparency per tile
- Deferred shading without a G-buffer (read lighting accumulation in-place)

**Vulkan subpasses** were an attempt to abstract this but added PSO complexity without delivering real cross-platform benefit. Vulkan 1.3 dynamic rendering + `VK_EXT_shader_tile_image` is the correct model.

---

## Shader Objects — Eliminating PSOs Entirely

`VK_EXT_shader_object` (Vulkan 1.3+, adopted in Roadmap 2024) removes the PSO entirely. Shaders are compiled individually; all state is set dynamically via commands.

```odin
// Load SPIR-V directly — no PSO:
vert_shader := shader_create(vert_spirv, .Vertex,   entry = "main", name = "mesh_vert")
frag_shader := shader_create(frag_spirv, .Fragment, entry = "main", name = "mesh_frag")

// Per draw: bind shaders + set all state dynamically
cmd_set_shaders(cmd_buf, vert_shader, frag_shader)
cmd_set_raster_state(cmd_buf, Raster_State{
    topology         = .Triangle_List,
    cull_mode        = .Cull_CW,
    alpha_to_coverage = false,
})
cmd_set_depth_state(cmd_buf, Depth_State{mode = .Read | .Write, compare = .Less_Equal})
cmd_set_blend_state(cmd_buf, Blend_State{enable = false})
cmd_draw_indexed(cmd_buf, index_count, ...)
```

**Trade-offs**:

| Approach | PSO-based | Shader objects |
|----------|-----------|---------------|
| Compile time | At PSO creation (can stutter) | At shader creation (smaller, faster) |
| State changes | Requires new PSO or dynamic state extensions | All state dynamic |
| Mobile support | Universal | Some implementations carry overhead |
| Permutation count | Explodes with state combinations | Zero permutations |
| Adoption | Vulkan 1.0+, DX12, Metal | Vulkan 1.3+ (`VK_EXT_shader_object`) |

---

## Programmable Vertex Fetch — No Vertex Buffers

Legacy APIs exposed vertex buffer objects with format descriptors; the driver generated fixed-function vertex fetch hardware. Modern GPU compilers emulate vertex fetch with raw load instructions at the start of the vertex shader — no special hardware required.

**Consequence**: vertex layout is no longer part of the PSO. No permutation per vertex format.

```cpp
// Pseudocode — types are illustrative (float32x4 = float[4], uint8x4 = 4 packed bytes, etc.)
// GPU struct layout must match CPU layout exactly — use naturally-aligned types or explicit offsets.
// uint8x4 normals require explicit unpack in the shader (not natively float on all ISAs).
struct Vertex { float32x4 position; uint8x4 normal; uint16x2 uv; };

struct alignas(16) Data {
    float32x4x4 matrixMVP;
    const Vertex* vertices;  // GPU virtual address — must remain valid until GPU execution completes
};

// Vertex shader reads directly:
VertexOut main(uint32 vertexIndex : SV_VertexID, const Data* data) {
    Vertex v = data->vertices[vertexIndex];
    return {
        .position = data->matrixMVP * v.position,
        .uv       = v.uv,
    };
}
```

**Capabilities unlocked**:
- Branch over vertex streams (e.g., skinned vs. static in one shader)
- Custom indexing schemes (e.g., meshlet-local indices)
- Instancing without a dedicated instancing API — just index into an array of transforms
- Interleaved or struct-of-arrays layouts chosen at runtime, not baked into PSO

### Dual Data Pointers for Graphics Draws

Vertex and pixel shaders are separate entry points and can receive independent data pointers.

```cpp
// Pseudocode — types are illustrative
struct DataVertex { float32x4x4 mvp; const Vertex* vertices; };
struct DataPixel  { float32x4 color; uint32 textureIndex; };

// Shared data (same pointer to both stages):
gpuDrawIndexed(cmd, sharedData.gpu, sharedData.gpu, indices, count);

// Separate data per stage:
gpuDrawIndexed(cmd, dataVertex.gpu, dataPixel.gpu, indices, count);
// GPU pointers must remain valid until GPU execution completes (async — CPU free ≠ GPU safe free)
```

This replaces the legacy split between vertex buffers, constant buffers, and texture bindings with a single pointer-passing convention.

---

## API Sidebar

### Vulkan

| Version / Extension | What's dynamic | What's still baked |
|--------------------|---------------|--------------------|
| **Vulkan 1.0** | Viewport, scissor, stencil ref, depth bias (with `VK_DYNAMIC_STATE_DEPTH_BIAS` flag) | Everything else: topology, RT formats, MSAA, DS, blend, cull, vertex input |
| **Vulkan 1.3 core** (`VK_EXT_extended_dynamic_state` v1 promoted) | + cull mode, depth test/write/compare, stencil op, topology, front face | Shader IR, RT formats, MSAA, alpha-to-coverage, blend, vertex input |
| **`VK_EXT_extended_dynamic_state3`** (optional, not in 1.3 core) | + blend enable/equation/write-mask, MSAA sample count, alpha-to-coverage | Shader IR, RT formats |
| **`VK_EXT_vertex_input_dynamic_state`** (optional, not in 1.3 core) | + full vertex input layout | Shader IR, RT formats |
| **`VK_EXT_shader_object`** (Roadmap 2024) | Everything — no PSO | Nothing (shaders compiled individually) |

**Async PSO compilation**: The correct pattern is: (1) attempt `vkCreateGraphicsPipelines` with `VK_PIPELINE_CREATE_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT` against a warm `VkPipelineCache` — returns `VK_PIPELINE_COMPILE_REQUIRED` and a null handle on cache miss; (2) on cache miss, submit a background thread compile without the flag; (3) use a simpler fallback pipeline until the background compile completes and the handle is valid. Do not dereference the pipeline handle on `VK_PIPELINE_COMPILE_REQUIRED`.

### DX12

`D3D12_GRAPHICS_PIPELINE_STATE_DESC` has ~100 fields; depth-stencil, blend, and rasterizer state are all baked. Limited dynamic state:

| Dynamic state | How |
|--------------|-----|
| Stencil reference | `OMSetStencilRef` |
| Blend factor | `OMSetBlendFactor` |
| Depth bias | `RSSetDepthBias` (DX12 Agility SDK 1.613+) |
| Vertex/index buffers | `IASetVertexBuffers` / `IASetIndexBuffer` (always dynamic) |

No equivalent to `VK_EXT_shader_object`. PSO permutations are unavoidable for blend/DS/cull changes.

**Pipeline library**: `ID3D12PipelineLibrary` — serialize compiled PSOs to disk; reload without recompilation. Reduces stutter on subsequent runs.

### Metal

| Object | Behavior |
|--------|----------|
| `MTLRenderPipelineDescriptor` | Bakes: vertex/fragment functions, RT pixel formats, MSAA, blend state, alpha-to-coverage |
| `MTLDepthStencilState` | Separate object; set dynamically via `setDepthStencilState:` — command packet |
| `MTLRenderCommandEncoder.setCullMode:` | Dynamic |
| `MTLRenderCommandEncoder.setTriangleFillMode:` | Dynamic |
| `MTLRenderCommandEncoder.setViewport:` | Dynamic |

**Metal 3 Mesh Shaders**: topology is implicit in the mesh shader dispatch — no topology field in PSO.

**Argument Buffers (Metal 2+)**: reduce binding overhead; do not eliminate PSO permutations for blend/RT format changes.

---

## Common Bugs — Symptoms → Cause

| Symptom | Likely cause |
|---------|-------------|
| Frame stutter on first draw of a new material | PSO compiled on the draw call thread; move to background thread or precompile |
| Shader recompile triggered by depth-stencil change | Depth-stencil baked into PSO; switch to separate DS state object or dynamic state |
| Blend produces wrong result on mobile | Blend state not embedded in PSO; mobile TBDR requires baked blend or framebuffer fetch |
| Vertex data corrupted when switching vertex layout | Vertex layout baked into PSO; use programmable vertex fetch to decouple |
| `VK_EXT_shader_object` unavailable | Check `VkPhysicalDeviceShaderObjectFeaturesEXT.shaderObject`; fall back to PSO + dynamic state |
| PSO cache exceeds disk budget | Too many topology/RT-format permutations; audit which state combinations actually occur |
| Mixing PSO and shader object draws in one command buffer | Defined but subtle: whichever was bound last (pipeline or shader objects) takes effect for each draw call — the other is silently ignored. Audit draw call ordering; enable `VK_LAYER_KHRONOS_validation` to surface unexpected precedence |
| PSO creation unexpectedly slow despite pipeline cache | Missing `VK_PIPELINE_CREATE_DERIVATIVE_BIT` on PSO families; derivative PSOs share microcode with the base PSO and compile incrementally |

---

## What's Not Covered Here

| Topic | Where to look |
|-------|--------------|
| Mesh shaders and amplification shaders | External: Vulkan `VK_EXT_mesh_shader`, DX12 mesh shader docs |
| Ray tracing pipeline state (`VkRayTracingPipelineCreateInfoKHR`) | External: Khronos Vulkan ray tracing spec |
| Compute pipelines | Simpler — only shader IR + specialization constants; no rasterizer state |
| Tile-based deferred rendering architecture | External: ARM Mali GPU Best Practices, Apple Metal Optimization Guide |
| Descriptor set / root signature layout | Separate concern from pipeline state; see GPU binding model references |
