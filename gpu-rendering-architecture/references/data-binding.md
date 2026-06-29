# Data Binding: Passing Data to the GPU

Covers how data reaches GPU shaders: 64-bit GPU virtual addresses, the root-argument model, shared CPU/GPU struct headers, static/specialization constants, uniformity analysis, and wide loads. Read this when designing how a draw or dispatch receives its inputs, or when debugging register pressure and memory access patterns.

---

## 64-bit GPU Pointers vs. Buffer Handles

Legacy APIs bind data through opaque handles: a buffer object + byte offset, requiring descriptor creation, alignment queries, and API calls per binding. Modern APIs expose the GPU virtual address directly as a 64-bit integer.

| Model | Mechanism | Overhead | Pointer arithmetic | Composability |
|---|---|---|---|---|
| **Handle + offset** | Descriptor set / SRV binding | API call per binding, alignment query | None — offset only | Low — each buffer needs its own binding slot |
| **64-bit GPU VA** | `vkGetBufferDeviceAddress`, `MTLBuffer.gpuAddress` (Metal 3+, macOS 13+) | Zero after initial query | Full — `ptr + n * sizeof(T)` | High — pass arrays of pointers, build linked structures |
| **CUDA native** | `T*` kernel parameter | Zero | Full | Full — same as CPU pointer semantics |

```cpp
// Legacy (DX12 descriptor table): requires descriptor heap entry, descriptor creation, alignment
cmdList->SetGraphicsRootDescriptorTable(0, descriptorHeap->GetGPUDescriptorHandleForHeapStart());

// Modern (DX12 inline root descriptor): GPU VA placed directly in root signature — no heap entry
// SetGraphicsRootConstantBufferView IS the modern DX12 approach; it takes a GPU VA directly
cmdList->SetGraphicsRootConstantBufferView(0, buffer->GetGPUVirtualAddress() + 256);

// Modern (Vulkan BDA): get VA once, do arithmetic freely
// Buffer must be created with VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;
// allocation must use VkMemoryAllocateFlagsInfo with VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT.
// Without these flags, vkGetBufferDeviceAddress returns 0 — silent GPU fault or corruption.
VkDeviceAddress base = vkGetBufferDeviceAddress(device, &addrInfo);  // uint64
// Pass base + any offset as a push constant or root struct field — no descriptor needed
```

> **Safety:** GPU virtual addresses carry no hardware bounds enforcement on most architectures. An out-of-bounds dereference reads or writes arbitrary GPU memory. Validate offsets on the CPU before writing them into root structs. Add explicit bounds checks in the shader when the offset is derived from GPU-side data (indirect arguments, per-object indices). Vulkan validation layers (`VK_EXT_device_address_binding_report`) can catch violations during development but not at runtime in production.

**Why 64-bit pointers matter beyond convenience:**
- Functions can accept `T*` parameters — enables CUDA-style reusable library functions (sorts, reductions, scans) that work on any buffer.
- Groupshared memory can be aliased: cast `groupshared uint8[N]` to different struct types via pointer.
- Array-of-pointers: a single buffer of `uint64` addresses, indexed by thread ID, enables per-object data without descriptor arrays.

**HLSL/GLSL limitation:** No native pointer type. Workaround: store 64-bit VA as `uint64_t`, cast to struct pointer using `ByteAddressBuffer` (standard HLSL, SM 5.0+) or `vk::RawBufferLoad` (Vulkan HLSL extension). Metal MSL and CUDA have native pointer syntax.

### API Sidebar

| API | Get GPU address | Shader-side pointer | Notes |
|---|---|---|---|
| Vulkan 1.2+ | `vkGetBufferDeviceAddress()` → `VkDeviceAddress` (uint64) | GLSL: `uint64_t` + `GL_EXT_buffer_reference`; HLSL: `uint64_t` workaround | `VK_KHR_buffer_device_address` promoted to core in 1.2 |
| DX12 | `ID3D12Resource::GetGPUVirtualAddress()` → `D3D12_GPU_VIRTUAL_ADDRESS` | No native pointer in HLSL; pass as root CBV (inline descriptor in root sig) | Root descriptor = GPU VA placed directly in root signature |
| Metal 3+ | `MTLBuffer.gpuAddress` → `uint64` | MSL: `device T* ptr = (device T*)addr` — native cast | Available since macOS 13 / iOS 16 (Metal 3, WWDC 2022); argument buffers carry GPU addresses |
| CUDA | `cudaMalloc(&ptr)` | `T*` — native pointer, `__restrict__` for no-alias | All loads via L1/L2$; no separate descriptor path |

---

## Texel Buffers vs. Raw Loads

Two paths for reading structured data from a buffer in a shader. Raw loads are faster on modern GPUs for most data.

| Feature | Texel buffer (`Buffer<T>`) | Raw load (`ByteAddressBuffer.Load<T>`) |
|---|---|---|
| Hardware path | Routed through texture sampler unit | Direct L1$ path |
| Throughput | Up to 2× lower | Baseline |
| Latency | Up to 3× higher | Baseline |
| Type known at compile time | No — format specified at descriptor creation | Yes — template parameter |
| Codegen quality | Worse — format conversion in sampler | Better — compiler knows type, can fuse loads |
| Normalized format conversion | Yes — RGBA8_UNORM → float4 | No — manual unpack required |
| **Use when** | Need normalized format conversion | Everything else |

```hlsl
// Texel buffer — slower, sampler hardware path
Buffer<float4> texelBuf : register(t0);
float4 val = texelBuf[threadId.x];  // goes through sampler unit

// Raw load — faster, direct cache path
ByteAddressBuffer rawBuf : register(t1);
// NOTE: byte offset is uint32 — overflows silently for buffers > ~256MB.
// For large buffers, compute offset as uint64 or use RawBufferLoad with a 64-bit address.
float4 val = rawBuf.Load<float4>(threadId.x * 16);  // type known at compile time → better codegen

// Normalized conversion (only valid reason for texel buffer):
Buffer<unorm float4> normBuf : register(t2);
float4 color = normBuf[idx];  // RGBA8_UNORM → float4, hardware conversion
```

---

## Wide Loads and Struct Alignment

Packing struct fields to 128-bit boundaries lets the compiler emit one wide load per 4 floats instead of four separate 32-bit loads. This reduces instruction count and memory transaction overhead.

```cpp
// Bad: 8 separate 32-bit loads
struct Transform {
    float px, py, pz;   // 3 loads
    float scale;        // 1 load
    float rx, ry, rz, rw;  // 4 loads
};

// Good: 2 × 128-bit loads (4× instruction reduction)
struct alignas(16) Transform {
    float4 positionScale;  // xyz = position, w = scale — one 128-bit load
                           // NOTE: float3 + float does NOT pack as expected in HLSL cbuffer layout:
                           // float3 is padded to 16 bytes, so float after float3 lands at offset+16.
                           // Use float4 and pack scale into .w, or use ByteAddressBuffer raw loads.
    float4 rotation;       // quaternion — one 128-bit load
};
// Compiler emits: load128(base + 0), load128(base + 16)
```

**Narrow types and register packing:**

```cpp
// uint8x4 in one register vs. RGBA8_UNORM texel fetch in four registers
uint32 packed = rawBuf.Load<uint32>(offset);   // 1 register
uint8  r = (packed >> 0)  & 0xFF;
uint8  g = (packed >> 8)  & 0xFF;
uint8  b = (packed >> 16) & 0xFF;
uint8  a = (packed >> 24) & 0xFF;
// AMD SDWA / free modifiers: GPU can extract 8-bit/16-bit lanes without explicit unpack
```

| Packing strategy | Loads per struct | Registers used | When to use |
|---|---|---|---|
| Unaligned fields | N (one per field) | N | Never — always align |
| `alignas(16)` groups | N/4 | N/4 | Default for all structs passed to GPU |
| Narrow types (`uint8`, `uint16`) | Fewer (pack multiple fields per word) | Fewer | High-density data (vertex attributes, LUTs) |
| AoS + raw loads | Minimal | Minimal | Non-linear (random) access patterns |
| SoA + raw loads | Minimal | Minimal | Linear (sequential) access patterns |

---

## Root Arguments: Single Pointer Per Dispatch/Draw

Instead of binding many resources at individual slots, pass one pointer to a struct that contains all inputs. The GPU driver preloads the struct's leading fields into scalar registers before the wave launches.

```cpp
// Shared CPU/GPU header (same struct compiled for both):
struct alignas(16) Data {
    float16x4 color;      // 8 bytes — preloaded into scalar regs
    uint16x2  offset;     // 4 bytes — preloaded
    const uint8*  lut;    // 8 bytes — GPU pointer, preloaded
    const uint32* input;  // 8 bytes — GPU pointer, preloaded
    uint32*       output; // 8 bytes — GPU pointer, preloaded
    // SECURITY: output is writable. Never derive its value from GPU-written data
    // (indirect dispatch args, compute-written buffers) without CPU-side validation.
    // A corrupted output pointer is an arbitrary GPU memory write primitive.
};

// CPU side: allocate from bump allocator, write via CPU-mapped pointer
auto data = frameArena.allocate<Data>();
data.cpu->color  = {1.0f, 0.0f, 0.0f, 1.0f};
data.cpu->lut    = luts.gpu + 64;      // pointer arithmetic — no offset API
data.cpu->input  = inputBuffer.gpu;
data.cpu->output = outputBuffer.gpu;
// LIFETIME: GPU pointers in this struct are only valid while backing buffers are alive.
// Do not reset frameArena until a fence confirms the GPU has finished this dispatch.
// On non-coherent architectures (ARM/Apple Silicon), flush CPU writes before dispatch:
//   Metal: [buffer didModifyRange:NSMakeRange(0, sizeof(Data))];
//   Vulkan: use VK_MEMORY_PROPERTY_HOST_COHERENT_BIT or explicit vkFlushMappedMemoryRanges.

gpuDispatch(cmd, data.gpu, {128, 1, 1});  // pass GPU half of the ptr pair

// GPU kernel:
[groupsize = (64, 1, 1)]
void main(uint32x3 tid : SV_ThreadID, const Data* data) {
    uint32 val = data->input[tid.x];   // data->input already in scalar reg
    data->output[tid.x] = val;
}
```

**Root struct field ordering rules:**

| Rule | Reason |
|---|---|
| Most-accessed fields first | Some architectures limit the preloaded range (e.g., first 64–128 bytes) |
| `const` on root pointer | Driver may use uniform data path; prevents accidental writes |
| `restrict` / no-alias | Compiler proves loads are uniform → scalar register assignment |
| Fields beyond preload range | Compiler emits scalar/uniform memory loads — fast but not register-resident |

**Root pointer vs. push constants:**

| Mechanism | Max size | Indirection | Use |
|---|---|---|---|
| Vulkan push constants | 128–256 bytes | None — values in command stream | Small hot scalars (matrix index, frame counter) |
| DX12 root constants | 64 dwords (256 bytes) | None | Same |
| DX12 root CBV | Unlimited | One load (GPU VA in root sig) | Larger uniform structs |
| Root pointer model | Unlimited | One load (pointer → struct) | All inputs; GPU preloads leading fields into scalar regs anyway |

### API Sidebar

| API | Root data mechanism | Max inline size | Notes |
|---|---|---|---|
| Vulkan | Push constants (`vkCmdPushConstants`) | 128–256 bytes (device limit) | Bypass descriptor sets entirely; hot path for per-draw scalars |
| Vulkan BDA | Root struct via push constant (pass `VkDeviceAddress`) | 8 bytes for the pointer | Struct lives in GPU memory; pointer is the push constant |
| DX12 | Root constants (32-bit values) or root descriptor (GPU VA) | 256 bytes constants; unlimited via VA | Root CBV = uniform buffer at that VA; root SRV/UAV also available |
| Metal | `[[buffer(0)]]` binding or argument buffer | Per-stage buffer binding | `MTLBuffer.gpuAddress` in argument buffer = pointer model |
| CUDA | Kernel parameters | ~4 KB (device-dependent) | Passed by value; `__restrict__` for no-alias; struct fields in registers |

---

## Shared CPU/GPU Struct Headers

The root-argument model only works cleanly when the CPU and GPU agree on the struct layout. The standard pattern: one header file included by both C++ and the shader compiler.

```cpp
// data.h — included by C++ and HLSL/NOSL/MSL
// NOSL = the no_gfx_api shader language used in the Odin examples below
struct alignas(16) MeshData {
    float4x4      mvp;         // 64 bytes
    const Vertex* verts;       // 8 bytes — GPU pointer
    const uint32* indices;     // 8 bytes — GPU pointer
    uint32        vertCount;   // 4 bytes
    uint32        _pad[3];     // 12 bytes — explicit padding to 96-byte (16-byte-aligned) size
                               // uint32 _pad alone = 88 bytes total, NOT 16-byte aligned (88 % 16 = 8)
};
```

```odin
// Odin / NOSL example (leotmp/no_gfx_api pattern):
Vert_Data :: struct { verts: rawptr }  // rawptr = GPU virtual address

// Per-frame:
verts_data := gpu.arena_alloc(frame_arena, Vert_Data)
verts_data.cpu.verts = verts_local.gpu.ptr   // assign GPU VA of vertex buffer

gpu.cmd_draw_indexed(cmd_buf, verts_data, {}, indices_local)
// cmd_draw_indexed takes the .gpu half of the ptr pair

// NOSL shader:
Data :: struct { verts: []Vertex }  // slice = (ptr, len)
vert :: #vertex (vert_id: uint @vert_id, data: ^Data @data) -> Vert_Output {
    out.pos   = vec4(data.verts[vert_id].pos,   1.0)
    out.color = vec4(data.verts[vert_id].color, 1.0)
}
```

**Separate vertex/fragment structs** (when the two stages need different data):

```odin
Vertex_Data   :: struct { mvp: matrix[4,4]f32, verts: rawptr }
Fragment_Data :: struct { color: [4]f32, texture_idx: u32 }

vd := gpu.arena_alloc(frame_arena, Vertex_Data)
fd := gpu.arena_alloc(frame_arena, Fragment_Data)
vd.cpu.mvp          = camera_mvp
vd.cpu.verts        = mesh_verts.gpu.ptr
fd.cpu.color        = material_color
fd.cpu.texture_idx  = tex_id

gpu.cmd_draw_indexed(cmd_buf, vd, fd, indices)
// Pass same struct for both when sharing:
gpu.cmd_draw_indexed(cmd_buf, shared_data, shared_data, indices)
```

**Layout rules for shared headers:**

| Rule | Reason |
|---|---|
| `alignas(16)` on struct | Matches GPU 128-bit load granularity |
| Explicit padding fields | Avoid compiler-inserted padding that differs between C++ and shader compiler |
| GPU pointers as `uint64` / `rawptr` | Both sides agree on 8-byte field; shader casts to typed pointer |
| No virtual functions, no RTTI | GPU struct is plain data; vtable pointers break layout |
| Separate headers per stage | Vertex and fragment can have different structs; avoids unused fields in registers |

---

## Static / Specialization Constants

Constants baked into the pipeline at creation time. The driver compiles them into microcode — branches on constants are dead-code-eliminated, and constant pointer fields become hardcoded addresses in the instruction stream.

```cpp
// Shared header:
struct alignas(16) Constants {
    int32  qualityLevel;
    uint8* blueNoiseLUT;  // GPU pointer baked into microcode
    // LIFETIME: this pointer is baked into the pipeline at creation time.
    // The buffer must be allocated once and never freed or moved for the lifetime of the pipeline.
    // Do NOT use frame-arena or per-scene allocations here — only static/startup resources.
};

Constants constants { .qualityLevel = 2, .blueNoiseLUT = blueNoiseLUT.gpu };
GpuPipeline pipe = gpuCreateComputePipeline(shaderIR, &constants);

// GPU kernel — qualityLevel == 3 branch is dead code at qualityLevel = 2:
[groupsize = (8, 8, 1)]
void main(uint32x3 tid : SV_ThreadID, const Data* data, const Constants constants) {
    if (constants.qualityLevel == 3) {
        // Entire block eliminated from microcode at pipeline creation
        highQualityPath(data, constants.blueNoiseLUT);
    }
    // Only qualityLevel == 2 path exists in compiled microcode
    standardPath(data);
}
```

**Use cases:**

| Use case | Mechanism | Benefit |
|---|---|---|
| Quality / feature toggles | Bake platform tier into microcode | Zero-cost branch — eliminated, not predicted |
| Shader polymorphism | Branch on constant, reinterpret `const Data*` as different struct type | C++ inheritance layout: common header + variant tail; no virtual dispatch |
| Hardcoded GPU pointer | Bake LUT address into microcode | Eliminates one load per use — address is an immediate |
| PSO permutation reduction | One PSO + constants → driver specializes on demand | Replaces N PSOs with 1 PSO × N constant sets |

**Shader polymorphism pattern:**

```cpp
// Common header:
struct alignas(16) BaseData { uint32 type; /* ... common fields ... */ };

// Variant tails (same memory, different interpretation):
struct alignas(16) DiffuseData  : BaseData { float4 albedo; };
struct alignas(16) EmissiveData : BaseData { float4 emission; float intensity; };

// Constants select the variant:
struct alignas(16) Constants { int32 materialType; };

// Shader:
void main(const BaseData* data, const Constants constants) {
    if (constants.materialType == DIFFUSE) {
        const DiffuseData* d = (const DiffuseData*)data;  // reinterpret — no overhead in GPU shader
        // GPU shaders have no strict aliasing rules; this cast is valid in shader code.
        // On the CPU side, this is UB in C++ — use std::bit_cast or a union instead.
        // SECURITY: materialType must be set by the CPU, never derived from GPU-written data.
        // A wrong materialType reads fields at wrong offsets — type confusion, silent corruption.
        // ...
    }
    // EMISSIVE branch dead-code-eliminated when materialType == DIFFUSE
}
```

### API Sidebar

| API | Mechanism | Granularity | Notes |
|---|---|---|---|
| Vulkan | `VkSpecializationInfo` in `VkPipelineShaderStageCreateInfo` | Per pipeline stage | Map constant IDs to byte offsets in a data blob; driver specializes at `vkCreateComputePipeline` |
| DX12 | No direct equivalent; use root constants (runtime) or `#define` + shader recompile | Per shader | Workaround: generate HLSL with `#define QUALITY_LEVEL 2`, recompile |
| Metal | `MTLFunctionConstantValues` + `newFunctionWithName:constantValues:` | Per function | Native specialization; driver compiles specialized variant on first use |
| CUDA | `__constant__` memory (device-wide) or template parameters | Per kernel launch | Template params = compile-time specialization; `__constant__` = runtime uniform |
| NOSL / no_gfx_api | Constants struct passed at pipeline creation | Per pipeline | Same pointer model as root data; driver bakes values into microcode |

---

## Uniformity Analysis and Scalar Optimization

A value is **uniform** if it is identical across all lanes in a wave. Uniform values live in scalar registers (one copy per wave) rather than vector registers (one copy per lane). Scalar register pressure is lower; scalar loads have lower latency.

```
Wave (64 lanes):
  lane 0: data->input[0]   ← data pointer is UNIFORM (same for all lanes)
  lane 1: data->input[1]   ← threadId.x is DIVERGENT (different per lane)
  ...
  lane 63: data->input[63]

data pointer → scalar register (1 copy)
threadId.x  → vector register (64 copies)
data->input[threadId.x] → vector load (64 addresses, coalesced if sequential)
```

**How uniformity propagates:**

| Operation | Inputs | Output uniformity |
|---|---|---|
| Root pointer dereference | Uniform pointer | Uniform value (scalar load) |
| Arithmetic on uniforms | All uniform | Uniform |
| Arithmetic with any divergent | Any divergent | Divergent |
| `const` pointer field | Uniform struct | Uniform — compiler proves no write through this pointer |
| `restrict` / no-alias | — | Enables uniformity proof for loads |

**`const` + `restrict` on root pointer:**

```cpp
// const: shader cannot write through this pointer → compiler proves value doesn't change
// restrict: no other pointer aliases this memory → compiler can cache the load
// NOTE: __restrict__ is C++ / CUDA syntax. In HLSL, use [restrict] attribute or rely on const.
//       In GLSL, use the `restrict` qualifier on buffer references (no underscores).
void main(const Data* __restrict__ data) {
    // data->lut is loaded once into a scalar register, reused across all uses
    for (int i = 0; i < N; i++) {
        result[i] = data->lut[i];  // lut pointer loaded once, not per iteration
    }
}
```

**Dynamic uniform optimization (hardware):** When all lanes of a SIMD load present the same address, the memory controller detects this and issues a single-lane load, then replicates the result to all lanes. This is transparent to the shader — no annotation required — but `const` + `restrict` helps the compiler emit the scalar load path explicitly rather than relying on hardware detection.

**Uniformity rules of thumb:**

| Value | Uniform? | Register class |
|---|---|---|
| Root pointer | Yes | Scalar |
| Root struct fields (preloaded range) | Yes | Scalar |
| Root struct fields (beyond preload range) | Yes (after scalar load) | Scalar |
| `gl_WorkGroupID` / `SV_GroupID` | Yes (per wave) | Scalar |
| `gl_LocalInvocationID` / `SV_GroupThreadID` | No | Vector |
| Texture sample result | No (generally) | Vector |
| Loop counter (uniform bounds) | Yes | Scalar |

---

## Common Bugs — Symptoms → Cause

| Symptom | Likely cause |
|---|---|
| High register pressure, shader spills to memory | Structs not `alignas(16)`; wide loads not emitted; too many divergent values in registers |
| Texel buffer reads slower than expected | Using `Buffer<T>` instead of `ByteAddressBuffer.Load<T>` for non-normalized data |
| GPU pointer arithmetic produces wrong address | Forgot to multiply by `sizeof(T)`; pointer is `uint64` not typed pointer |
| Specialization constant branch not eliminated | Constant not passed via `VkSpecializationInfo` / `MTLFunctionConstantValues`; passed as push constant instead |
| Root struct fields reloaded every iteration | Missing `const` or `restrict` on root pointer; compiler can't prove value is stable |
| Struct layout mismatch between CPU and GPU | Implicit padding differs between C++ compiler and shader compiler; use explicit `_pad` fields |
| Uniform load not promoted to scalar register | Value derived from divergent input; check uniformity propagation chain |
| GPU fault / silent memory corruption | Buffer created without `VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT`; `vkGetBufferDeviceAddress` returns 0 |
| Dangling GPU pointer, wrong data after arena reset | Frame arena reset before GPU fence; backing buffer freed while GPU still reading |
| `ByteAddressBuffer.Load` reads wrong address | Byte offset overflows uint32 for buffers > ~256MB; compute offset as uint64 |
| `float3` + `float` in HLSL cbuffer doesn't pack | `float3` in cbuffer is padded to 16 bytes; `float` after `float3` lands at offset+16, not +12; use `float4` |
| GPU reads stale CPU data (ARM/Apple Silicon) | CPU writes to GPU-visible memory not flushed; call `[MTLBuffer didModifyRange:]` or `vkFlushMappedMemoryRanges` |

---

## What's Not Covered Here

| Topic | Where to look |
|---|---|
| Descriptor sets / bindless texture arrays | GPU-driven rendering reference (bindless indexing) |
| Indirect draw / compute (GPU-driven) | GPU-driven rendering reference |
| Memory barriers and synchronization | Synchronization reference |
| Buffer suballocation and bump allocators | Memory management reference |
| Shader compilation and PSO caching | Pipeline state reference |
