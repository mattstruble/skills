# Bindless Textures: Descriptor Heaps and Non-Uniform Access

Covers descriptor heap layout, 32-bit index vs 64-bit handle tradeoffs, non-uniform texture access and scalarization, descriptor creation and write flow, embedded samplers, and rasterizer metadata (why GpuTexture still exists). Read this when implementing a material system, deferred shading, or ray tracing that requires per-pixel or per-hit texture selection.

Source: Sebastian Aaltonen, "No Graphics API" blog post; `leotmp/no_gfx_api` Odin implementation.

---

## Descriptor Heap Layout

A **descriptor** is an opaque hardware blob encoding everything the sampler unit needs to fetch from a texture: dimensions, format, mip count, GPU memory address, compression metadata. On most hardware this is **256 bits (32 bytes)**.

A **descriptor heap** is a contiguous array of these blobs in GPU-visible memory. All shaders index into it by slot number.

```
Descriptor Heap (GPU memory)
┌──────────────────────────────────────────────────────────────────┐
│ slot 0 │ slot 1 │ slot 2 │ ... │ slot N │  (each = 256 bits)    │
└──────────────────────────────────────────────────────────────────┘
         ↑
   heap_base + index * 32 bytes
```

### Two Hardware Implementations

| Vendor | Mechanism | Descriptor location | Non-uniform cost |
|---|---|---|---|
| **AMD, ARM** | Scalar-register descriptors | 8 scalar registers per shader invocation | Scalarization loop: one masked sampler round-trip per unique index value |
| **Nvidia, Apple, Qualcomm, Intel** | Indexed heap | 32-bit index per lane; sampler fetches descriptor at `heap_base + index * 32` | Per-lane index in sample instruction; sampler loops internally |

**Sampler descriptor cache**: indexed-heap hardware maintains a small internal cache (typically 4–8 entries). Accessing more than ~8 unique textures in a single wave/warp increases cache pressure.

> **API sidebar**
> - Vulkan: `VK_EXT_descriptor_buffer` — descriptor buffer bound via `vkCmdBindDescriptorBuffersEXT`; layout size queried with `vkGetDescriptorSetLayoutSizeEXT`
> - DX12: `ID3D12Device::CreateDescriptorHeap`; heap type `D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV`
> - Metal: driver manages heap internally; user accesses via `gpuResourceID` (see §32-bit Index vs 64-bit Handle)

---

## 32-bit Index vs 64-bit Handle

| Approach | Size per reference | 5 textures | Contiguous range? | API |
|---|---|---|---|---|
| **32-bit index** | 4 bytes | 20 bytes | Yes — `base + offset` | DX12 SM6.6, Vulkan descriptor_buffer |
| **64-bit handle** | 8 bytes | 40 bytes | No — each needs its own handle | Metal 3+ `gpuResourceID` |
| **256-bit descriptor** | 32 bytes | 160 bytes | N/A (inline) | AMD scalar registers |

**Why 32-bit index wins for material systems**: store one `textureBase` index per material; derive color/normal/PBR textures by addition. No per-texture handle storage, no indirection table.

> **Overflow warning**: `base + offset` is unsigned 32-bit arithmetic. If `base` is allocated near heap capacity, `base + N` silently wraps to a low slot index and samples the wrong texture — no error is produced. The allocator must reserve a guard band of `max_offset` slots at the top, or validate `base + max_offset < heap_size` at allocation time.

```cpp
struct Material {
    uint32 textureBase;  // color = base+0, normal = base+1, pbr = base+2
    float4 baseColor;
    float  roughness;
    float  metallic;
};
// Shader: textureHeap[material.textureBase + 0], [+1], [+2]
```

**Metal 3+ limitation**: `texture.gpuResourceID` is a 64-bit opaque handle. You cannot represent a contiguous range — each texture requires its own stored handle. Embed handles directly in argument buffers or GPU structs; `residencySet` replaces the old `useResource` call.

---

## Non-Uniform Texture Access and Scalarization

**Uniform access**: all lanes in a wave sample the same texture. Trivially fast on all hardware — no annotation needed.

**Non-uniform access**: each lane may sample a different texture (deferred shading: per-pixel material; ray tracing: per-hit material). Requires `NonUniformResourceIndex` annotation.

```cpp
// Uniform case — all lanes use the same terrain texture
Texture tex = textureHeap[data->terrainTextureIndex];
float4 color = sample(tex, sampler, uv);  // no annotation needed

// Non-uniform case — each lane may have a different material
uint32 texBase = NonUniformResourceIndex(material.textureBase);
Texture texColor  = textureHeap[texBase + 0];
Texture texNormal = textureHeap[texBase + 1];
Texture texPBR    = textureHeap[texBase + 2];

float4 color  = sample(texColor,  sampler, uv);
float4 normal = sample(texNormal, sampler, uv);
float4 pbr    = sample(texPBR,    sampler, uv);
```

### What `NonUniformResourceIndex` Does Per Vendor

| Vendor | Behavior | Cost |
|---|---|---|
| Nvidia, Apple, Qualcomm (per-lane mode) | Emits per-lane index in sample instruction; sampler loops internally | Low — hardware handles divergence |
| AMD, ARM (uniform-only sampler) | Emits scalarization loop: extract one lane, execute, merge, repeat | Higher — O(unique indices) sampler round-trips |

**Buffer data**: non-uniform buffer access via 64-bit pointers is free — no `NonUniformResourceIndex` needed. The annotation is only required when indexing the **texture heap**.

```cpp
// Per-lane material pointer — no annotation needed
Material* material = data->materialMap[threadId.xy];
uint32 textureBase = NonUniformResourceIndex(material.textureBase);
//                   ^^ only here, when indexing the texture heap
```

> **API sidebar**
> - HLSL: `NonUniformResourceIndex(index)` wraps the index expression
> - GLSL/Vulkan: `nonuniformEXT(index)` from `GL_EXT_nonuniform_qualifier`
> - Metal: no annotation — hardware handles non-uniform access natively
> - WGSL: no equivalent yet; non-uniform indexing is restricted

---

## Descriptor Creation and Heap Write Flow

```cpp
// 1. Allocate the heap (user-managed GPU memory)
GpuTextureDescriptor *textureHeap = gpuMalloc<GpuTextureDescriptor>(65536);

// 2. Describe and allocate the texture
GpuTextureDesc textureDesc {
    .dimensions = img.dimensions,
    .format     = FORMAT_RGBA8_UNORM,
    .usage      = SAMPLED,
};
GpuTextureSizeAlign sizeAlign = gpuTextureSizeAlign(textureDesc);
void *texturePtr = gpuMalloc(sizeAlign.size, sizeAlign.align, MEMORY_GPU);
GpuTexture texture = gpuCreateTexture(textureDesc, texturePtr);

// 3. Write descriptor into heap slot
textureHeap[slotIndex] = gpuTextureViewDescriptor(texture, { .format = FORMAT_RGBA8_UNORM });

// 4. Upload image data
gpuCopyToTexture(uploadCmdBuf, texturePtr, uploadPtr, texture);

// 5. Barrier — invalidates sampler's internal descriptor cache
gpuBarrier(uploadCmdBuf, STAGE_TRANSFER, STAGE_ALL, HAZARD_DESCRIPTORS);

// 6. Bind heap before draws/dispatches
gpuSetActiveTextureHeapPtr(commandBuffer, gpuHostToDevicePointer(textureHeap));
```

### Descriptor Invalidation

Emit `HAZARD_DESCRIPTORS` whenever descriptors are written (CPU or GPU side). This invalidates the sampler's tiny internal cache. Not needed between frames if descriptors are unchanged.

### Odin API (from `leotmp/no_gfx_api`)

```odin
// Heap creation
heap := desc_heap_create(
    texture_count    = 65536,
    texture_rw_count = 65536,
    sampler_count    = 32,
    bvh_count        = 16,
    name             = "main_heap",
)

// Writing descriptors
desc_heap_set_textures(heap, start_idx, []Texture_Descriptor{...})
desc_heap_set_samplers(heap, start_idx, []Sampler_Descriptor{...})

// Creating descriptors
tex_desc := texture_view_descriptor(texture, Texture_View_Desc{.format = .RGBA8_UNORM})
smp_desc := sampler_descriptor(Sampler_Desc{.min_filter = .LINEAR, ...})

// Thread-safe pool allocator — returns contiguous range start index
// (thread-safety covers CPU-side index allocation only; see note below)
idx := desc_pool_alloc_textures(&pool, []Texture_Descriptor{color, normal, pbr})
// Shader: heap[idx+0]=color, heap[idx+1]=normal, heap[idx+2]=pbr
// Safe free: ensure no in-flight GPU commands reference this slot.
// Defer free until the frame fence for the last referencing command buffer
// has signaled. Freeing while commands are in flight causes the slot to be
// reallocated and sampled as a different texture.
desc_pool_free_textures(&pool, idx)

// Bind for a command buffer
cmd_set_desc_heap(cmd_buf, heap)
```

> **Thread-safety scope**: the pool allocator is thread-safe for CPU-side index allocation only. Writing descriptors to GPU-visible heap memory (`desc_heap_set_textures`) while a command buffer that reads those slots is in flight is a GPU data race — distinct from the `HAZARD_DESCRIPTORS` barrier (which handles CPU→GPU cache coherency, not concurrent CPU writes vs. GPU reads). A background streaming thread must either: (a) write to slots not referenced by any in-flight command buffer, (b) double-buffer the slot, or (c) wait for the referencing command buffer's fence before overwriting.

> **API sidebar**
> - Vulkan `VK_EXT_descriptor_buffer`: CPU writes directly to descriptor buffer memory; `vkGetDescriptorEXT` fills the blob; `vkCmdBindDescriptorBuffersEXT` binds; `vkCmdSetDescriptorBufferOffsetsEXT` sets per-set offsets
> - DX12 SM6.6: CPU writes via `CopyDescriptors` / `CreateShaderResourceView` into heap; GPU can write descriptors in SM6.6+; `SetDescriptorHeaps` binds; shader accesses `ResourceDescriptorHeap[index]` directly
> - Metal 3+: `texture.gpuResourceID` returns 64-bit handle; embed in argument buffer or GPU struct; `residencySet.addAllocation(texture)` makes it resident; no explicit heap bind call

---

## Embedded / Inline Samplers

For common filtering modes, encode sampler parameters as shader constants — no sampler heap needed.

```cpp
// Embedded sampler — compiler encodes parameters as shader constants
Sampler sampler = {
    .minFilter = LINEAR,
    .magFilter = LINEAR,
    .mipFilter = LINEAR,
    .addressU  = CLAMP,
    .addressV  = CLAMP,
};
float4 color = sample(texture, sampler, uv);
```

| Criterion | Embedded sampler | Sampler descriptor heap |
|---|---|---|
| Parameters known at | Pipeline creation | Runtime |
| API overhead | None — compiler constant | Heap allocation + descriptor write |
| Dynamic anisotropy (user setting) | Not possible | Required |
| Typical use | Fixed filtering (linear, nearest, clamp) | User-configurable quality settings |

> **API sidebar**
> - HLSL: `SamplerState` declared as `static const` in shader; DX12 static sampler in root signature
> - Metal: `constexpr sampler` in shader source
> - Vulkan: immutable samplers in `VkDescriptorSetLayoutBinding`; or inline uniform block

---

## GpuTexture: Rasterizer Metadata

The rasterizer output stage (render targets, depth/stencil) is **not yet bindless**. `gpuBeginRenderPass` needs a CPU-side texture object to build command packets for clear, load/store, and resolve operations. The 256-bit GPU descriptor alone is insufficient — it encodes only sampling parameters, not rasterizer setup metadata.

`GpuTexture` is the minimum CPU object: it holds driver-specific data for rasterizer configuration. It is not needed for shader sampling — that goes through the heap.

| Operation | What's needed | Why |
|---|---|---|
| Shader sampling | Heap slot index (32-bit) | Sampler reads descriptor from heap |
| Render target / depth attachment | CPU `GpuTexture` object | Rasterizer setup requires driver metadata |
| Descriptor creation | CPU `GpuTexture` object | `gpuTextureViewDescriptor(texture, ...)` |
| Streaming mip swap | Write new descriptor at slot + `HAZARD_DESCRIPTORS` | No pipeline stall — just cache invalidate |

---

## Common Patterns

### Material System with Contiguous Ranges

```cpp
// Offline: pack material textures into contiguous heap slots
// Shader: material.textureBase + offset
// Heap management: freelist of ranges; group by material

// Allocation (Odin):
base := desc_pool_alloc_textures(&pool, []Texture_Descriptor{color, normal, pbr})
material.textureBase = base
// Free when material is unloaded:
desc_pool_free_textures(&pool, material.textureBase)
```

### Streaming Textures

```
Low-res mip always resident in heap slot.
High-res mip streams in:
  1. Upload high-res data to GPU
  2. Write new descriptor at same slot
  3. gpuBarrier(HAZARD_DESCRIPTORS)
  → No pipeline stall; sampler cache invalidated; next sample uses high-res
```

### Deferred Shading (Non-Uniform Access Pattern)

```
G-buffer pass:  write material ID per pixel (uniform texture access per draw)
Lighting pass:  read material ID → index texture heap (non-uniform)
                NonUniformResourceIndex(materialId) on all texture heap accesses
```

---

## Common Bindless Bugs

| Symptom | Cause | Fix |
|---|---|---|
| Wrong texture on some pixels in deferred pass | Missing `NonUniformResourceIndex` on heap index | Annotate all non-uniform heap indices |
| Stale texture after streaming update | Missing `HAZARD_DESCRIPTORS` barrier after descriptor write | Emit barrier after every heap write |
| Crash or corruption on AMD with non-uniform access | Scalarization loop not triggered — annotation missing | Add `NonUniformResourceIndex`; verify HLSL SM6.6 target |
| Metal: texture not visible in shader | `residencySet` not updated after adding texture | Call `residencySet.addAllocation(texture)` before encoding |
| DX12: heap index out of range | Heap created too small; pool allocator overflowed | Size heap to max concurrent textures; add hard upper bound in pool. **GPU provides no bounds checking** — out-of-bounds reads produce undefined results (wrong texture, silent corruption, or GPU hang/TDR), not a CPU exception. A debug assert is insufficient; the allocator must enforce a hard limit. |
| Descriptor cache thrash (poor perf, many unique textures per wave) | Wave accesses >8 unique textures | Sort draw calls by material; reduce texture variety per wave |
