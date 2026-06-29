# GPU Memory Model

Covers GPU memory topology, the three allocation types, the CPU/GPU dual-pointer model, arena allocators for per-frame data, and the copy-to-private path for textures and compressed buffers. Read this when allocating GPU resources, uploading mesh/texture data, or designing a frame memory strategy.

Source material: [Sebastian Aaltonen — "No Graphics API"](https://iolite-engine.com/blog_posts/no_graphics_api); [`leotmp/no_gfx_api` Odin implementation](https://github.com/leotmp/no_gfx_api).

---

## Hardware Topology

Three physical configurations determine whether a CPU write reaches GPU memory directly or requires a DMA copy.

| Topology | CPU→GPU path | Notes |
|---|---|---|
| **UMA** (integrated GPU) | Direct — shared physical memory | No copy needed. CPU writes are immediately visible to GPU. Mobile, Apple Silicon, Intel integrated. |
| **Discrete + ReBAR** | Direct — entire GPU heap mapped to CPU address space | NVIDIA: Resizable BAR. AMD: Smart Access Memory. Requires BIOS + OS + driver support. PCIe 4.0+ recommended. |
| **Discrete, no ReBAR** | DMA copy — only a 256 MB BAR window is CPU-accessible | Legacy path. All uploads go through a staging buffer in the BAR window. |

**Practical consequence**: on ReBAR/UMA, CPU writes to `MEMORY_DEFAULT` allocations reach the GPU without any explicit copy command. On no-ReBAR hardware, the driver handles the BAR window internally — the allocation API is the same, but throughput is lower.

---

## Memory Types

Three types cover all allocation needs. Default is almost always correct.

| Type | CPU access | GPU access | Use for |
|---|---|---|---|
| `MEMORY_DEFAULT` | Write-combined (persistently mapped) | Fast read | Uniforms, draw arguments, descriptor tables, small uploads, per-frame scratch |
| `MEMORY_GPU` | None | Fast read/write + compression | Textures, large persistent vertex/index buffers, render targets |
| `MEMORY_READBACK` | Cached read | Slow write (cache coherency overhead) | Screenshots, virtual texture feedback, GPGPU result readback |

**Write-combined** means CPU writes bypass the CPU cache and go directly to the PCIe bus (or UMA memory). Sequential writes are fast; random reads from the CPU are slow. Never read back from `MEMORY_DEFAULT` on the CPU.

**Write sequentially into write-combined memory.** WC buffers flush in cache-line-sized chunks. Non-sequential writes (scattered field writes, `memset` followed by random field updates) cause partial flushes and can be significantly slower. Prefer: populate a struct on the CPU stack, then `memcpy` the whole struct into the GPU allocation.

**`MEMORY_GPU` enables hardware compression** that is unavailable to CPU-written memory:
- **DCC (Delta Color Compression)**: lossless compression in the ROP path. Only the GPU copy engine produces DCC-compressed data. Display engine and texture samplers read it transparently.
- **Morton/Z-order swizzle**: GPU texture caches are 2D-locality-optimized. Textures are stored in Morton order, not row-major. The copy engine performs this transformation during upload.
- **Generic buffer compression**: available on some architectures for GPU-private buffers. Also requires the copy path.

---

## Allocation API

A CUDA-style flat allocator. Default alignment is 16 bytes (vec4). Override for specific needs.

```cpp
// Allocate persistently-mapped GPU memory (MEMORY_DEFAULT)
uint32* numbers = gpuMalloc(1024 * sizeof(uint32));

// CPU writes directly — no staging, no copy command
for (int i = 0; i < 1024; i++) numbers[i] = random();

gpuFree(numbers);

// Override alignment (e.g., for texture size/align requirements)
void* buf = gpuMalloc(size, alignment);

// GPU-private allocation (textures, large meshes)
void* meshGpu = gpuMalloc(mesh.byteSize, MEMORY_GPU);
```

In Odin (`leotmp/no_gfx_api`):

```odin
Memory :: enum { Default = 0, GPU, Readback }

// Type-safe slice allocation
verts := gpu.mem_alloc(Vertex, 3)               // MEMORY_DEFAULT
verts_local := gpu.mem_alloc(Vertex, 3, .GPU)   // MEMORY_GPU

// Raw allocation
buf := gpu.mem_alloc_raw(el_size, el_count, align, .Default)

gpu.mem_free(verts)
gpu.mem_free_raw(buf)
```

---

## The Two-Pointer Problem

A `MEMORY_DEFAULT` allocation has two addresses: the CPU virtual address (used for writes) and the GPU virtual address (used in shader commands and descriptor tables). These are **not** the same value.

```cpp
// gpuHostToDevicePointer: translates CPU virtual → GPU virtual
// Call once per allocation, cache the result — do not call per-frame
struct GpuAlloc { void* cpu; void* gpu; };

GpuAlloc alloc;
alloc.cpu = gpuMalloc(size);
alloc.gpu = gpuHostToDevicePointer(alloc.cpu);

// Pointer arithmetic works on GPU pointers — no separate offset API needed
data.cpu->lut = luts.gpu + 64;   // GPU pointer offset
```

In Odin, the `ptr` type bundles both addresses:

```odin
ptr :: struct { cpu: rawptr, using gpu: gpuptr }
gpuptr :: struct { ptr: rawptr, _impl: [2]u64 }

// Write via .cpu, pass .gpu to draw commands
verts_data.cpu.verts = verts_local.gpu.ptr
gpu.cmd_draw_indexed(cmd_buf, verts_data, {}, indices_local)
```

**Rule**: write through `.cpu`; pass `.gpu` to any GPU command or descriptor. Never pass a `.cpu` pointer to a shader — it will fault or silently read garbage.

**Dangling GPU pointer**: the GPU virtual address is invalidated when `gpuFree` is called on the CPU allocation. Do not cache `.gpu` in descriptor tables or shader arguments beyond the allocation's lifetime. Descriptor tables referencing freed GPU memory will read garbage or fault.

---

## Arena Allocator (Per-Frame Data)

Per-frame GPU data (uniforms, draw argument buffers, descriptor tables) is allocated from an arena and freed at the start of the next use of that frame slot. This avoids per-allocation overhead and eliminates explicit free tracking.

```odin
// One arena per frame-in-flight
Frames_In_Flight :: 2
frame_arenas: [Frames_In_Flight]gpu.Arena
for &a in frame_arenas do a = gpu.arena_init()  // default: 4 MiB, MEMORY_DEFAULT

// Each frame:
frame_arena := &frame_arenas[next_frame % Frames_In_Flight]
gpu.fence_wait(frame_fences[next_frame % Frames_In_Flight])  // confirm GPU done with this slot
gpu.arena_free_all(frame_arena)   // safe to reclaim now

// Allocate per-frame data
uniforms := gpu.arena_alloc(frame_arena, SceneUniforms)
uniforms.cpu.view_proj = camera.view_proj

draw_args := gpu.arena_alloc(frame_arena, DrawArgs, draw_count)
```

Arena API:

```odin
arena_init:     proc(block_size: i64 = 4*1024*1024, mem_type := Memory.Default) -> Arena
arena_alloc:    proc(arena: ^Arena, $T: typeid) -> ptr_t(T)
arena_alloc:    proc(arena: ^Arena, $T: typeid, count: i32) -> slice_t(T)
arena_free_all: proc(arena: ^Arena)   // resets offset; does not release backing memory
arena_destroy:  proc(arena: ^Arena)   // releases backing memory
```

**Frame-in-flight safety**: `arena_free_all` must only be called after the GPU has finished reading from that frame's allocations. Use a fence or semaphore to confirm the previous submission using this slot has completed before calling `arena_free_all`.

---

## Uploading to GPU-Private Memory

`MEMORY_GPU` allocations cannot be written by the CPU. The upload path is: write to a CPU-mapped staging allocation → issue a copy command → the copy engine performs DCC compression and Morton swizzle.

### Buffer Upload

```cpp
// 1. Write to staging (CPU-mapped)
auto upload = uploadBumpAllocator.allocate(mesh.byteSize);
mesh.load(upload.cpu);

// 2. Allocate GPU-private destination
void* meshGpu = gpuMalloc(mesh.byteSize, MEMORY_GPU);

// 3. Copy — performs generic buffer compression if supported
gpuMemCpy(commandBuffer, meshGpu, upload.gpu);
// WARNING: keep `upload` alive until the GPU signals completion of commandBuffer.
// Freeing the staging allocation (or resetting the staging arena) before the copy
// engine finishes reading it causes silent corruption or a GPU fault.
```

In Odin:

```odin
// Staging arena (MEMORY_DEFAULT)
arena := gpu.arena_init()
verts := gpu.arena_alloc(&arena, Vertex, 3)
verts.cpu[0].pos = { -0.5,  0.5, 0.0 }
verts.cpu[1].pos = {  0.5,  0.5, 0.0 }
verts.cpu[2].pos = {  0.0, -0.5, 0.0 }

// GPU-private destination
verts_local := gpu.mem_alloc(Vertex, 3, .GPU)

// Upload
upload_cmd := gpu.commands_begin(.Main)
gpu.cmd_mem_copy(upload_cmd, verts_local, verts)
gpu.cmd_barrier(upload_cmd, .Transfer, .All, {})
gpu.queue_submit(.Main, { upload_cmd })
// WARNING: arena must stay alive until the GPU signals upload_cmd completion.
// Do not call arena_free_all or arena_destroy until the upload fence fires.
```

### Texture Upload

Textures require size and alignment queried from the API — the GPU layout depends on format, dimensions, and mip levels.

```cpp
GpuTextureDesc desc {
    .dimensions = pngImage.dimensions,
    .format     = FORMAT_RGBA8_UNORM,
    .usage      = SAMPLED,
};

// Query required size and alignment for this texture
GpuTextureSizeAlign sa = gpuTextureSizeAlign(desc);
void* texPtr = gpuMalloc(sa.size, sa.align, MEMORY_GPU);
GpuTexture tex = gpuCreateTexture(desc, texPtr);

// Write decoded pixels to staging, then copy
// Use raw pixel size for staging (width × height × bytes_per_pixel), not sa.size.
// sa.size is the GPU layout size (Morton-swizzled) and may be larger than the linear data.
auto upload = uploadBumpAllocator.allocate(pngImage.width * pngImage.height * 4);
decodePng(pngImage, upload.cpu);
gpuMemCpy(uploadCmdBuf, texPtr, upload.gpu);

// Barrier: make texture visible to samplers before first draw
gpuBarrier(uploadCmdBuf, STAGE_TRANSFER, STAGE_ALL, HAZARD_DESCRIPTORS);
```

**Why the barrier**: the copy engine and the shader pipeline are separate hardware units. Without a barrier, the sampler may read the texture before the copy engine has written it. `HAZARD_DESCRIPTORS` covers the descriptor-read hazard.

### Why CPU Cannot Write Directly to GPU-Private

| Reason | Detail |
|---|---|
| **Morton swizzle** | GPU texture caches use 2D-locality-optimized (Z-order) layout. Row-major data written by CPU would be read with cache misses on every access. The copy engine performs the swizzle. |
| **DCC compression** | Lossless delta compression in the ROP path. Only the GPU copy engine can produce valid DCC metadata. CPU-written data cannot be DCC-compressed. |
| **Generic buffer compression** | Some architectures compress GPU-private buffers. Requires the copy path. |
| **Exception** | `VK_EXT_host_image_copy`: driver performs swizzle on CPU; available on discrete GPUs (driver handles DMA internally); no DCC support. Promoted to Vulkan 1.4 core. |

---

## Alignment

| Scenario | Alignment |
|---|---|
| Default (uniforms, draw args, descriptors) | 16 bytes (vec4) |
| Textures | Query `gpuTextureSizeAlign(desc)` — depends on format, dimensions, mip count |
| Vertex/index buffers | 4 bytes (index) or 16 bytes (vertex, for vec4 alignment) |
| Constant/uniform buffers | 256 bytes (DX12 CBV requirement; Vulkan: `minUniformBufferOffsetAlignment`) |

Always query texture alignment — do not assume. Incorrect alignment causes GPU faults or silent corruption.

---

## Common Bugs

| Symptom | Cause | Fix |
|---|---|---|
| GPU reads stale data after upload | Missing barrier after copy command | Add `gpuBarrier(STAGE_TRANSFER, STAGE_ALL, HAZARD_DESCRIPTORS)` after copy |
| GPU fault / crash on texture sample | Texture allocated with wrong alignment | Query `gpuTextureSizeAlign` and use returned `.align` |
| CPU reads garbage from GPU allocation | Reading from write-combined `MEMORY_DEFAULT` | Never CPU-read from `MEMORY_DEFAULT`; use `MEMORY_READBACK` for readback |
| Shader receives wrong pointer | Passing `.cpu` address to GPU command | Pass `.gpu` (device address) to all GPU commands and descriptors |
| Arena data corrupted mid-frame | `arena_free_all` called before GPU finished | Fence/semaphore: confirm GPU completion before freeing the arena slot |
| Texture appears corrupted / wrong colors | CPU wrote directly to `MEMORY_GPU` | Use staging + copy; `MEMORY_GPU` is not CPU-writable |
| Mesh/texture data corrupted after upload | Staging buffer freed before GPU copy completed | Keep staging allocation live until upload fence signals; reset staging arena only after GPU completion |
| Shader reads garbage after resource update | Descriptor table holds stale GPU pointer to freed allocation | Rebuild/update descriptor table entries when reallocating resources |
| Readback buffer contains stale/zero data | CPU read before GPU copy completed | Wait on the readback fence/semaphore before accessing `MEMORY_READBACK` allocation |

---

## API Sidebar

### Memory Type Mapping

| Concept | Vulkan | DX12 | Metal | CUDA |
|---|---|---|---|---|
| `MEMORY_DEFAULT` (CPU-mapped) | `HOST_VISIBLE \| HOST_COHERENT` heap | `D3D12_HEAP_TYPE_UPLOAD` | All memory CPU-accessible (UMA) | `cudaMallocHost` (pinned) |
| `MEMORY_DEFAULT` on ReBAR/UMA | `DEVICE_LOCAL \| HOST_VISIBLE` heap | `D3D12_HEAP_TYPE_GPU_UPLOAD` (2023) | Same — no distinction | — |
| `MEMORY_GPU` (GPU-private) | `DEVICE_LOCAL` only heap | `D3D12_HEAP_TYPE_DEFAULT` | Driver-managed (no explicit type) | `cudaMalloc` |
| `MEMORY_READBACK` | `HOST_VISIBLE \| HOST_CACHED` heap | `D3D12_HEAP_TYPE_READBACK` | `MTLStorageModeShared` with CPU read | `cudaMallocHost` (pinned) + `cudaMemcpy(DeviceToHost)` |

### GPU Pointer / Device Address

| API | How to get GPU virtual address |
|---|---|
| Vulkan | `VK_KHR_buffer_device_address` → `vkGetBufferDeviceAddress` |
| DX12 | `ID3D12Resource::GetGPUVirtualAddress()` |
| Metal | `MTLBuffer.gpuAddress` (macOS 13+ / iOS 16+) |
| CUDA | `cudaHostGetDevicePointer(hostPtr, 0)` |

### Texture Size/Alignment Query

| API | Query |
|---|---|
| Vulkan | `vkGetImageMemoryRequirements` → `.size`, `.alignment` |
| DX12 | `ID3D12Device::GetResourceAllocationInfo` |
| Metal | `MTLDevice.heapTextureSizeAndAlign(descriptor:)` |

### Host Image Copy (Skip Staging)

| API | Support |
|---|---|
| Vulkan | `VK_EXT_host_image_copy` — driver swizzles on CPU; available on discrete GPUs; no DCC; Vulkan 1.4 core |
| DX12 | `WriteToSubresource` — UMA only |
| Metal | Always available (UMA architecture) |
