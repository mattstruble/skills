# GPU Synchronization and Barriers

Modern GPU synchronization: stage-based barriers, hazard flags, split barriers, timeline semaphores, and transient command buffers. Synthesized from Sebastian Aaltonen's "No Graphics API" blog post and the `leotmp/no_gfx_api` Odin implementation.

**Relationship to other references**: This covers the *synchronization model* — how to express ordering and cache coherence between GPU work. For resource management and memory allocation, see `memory-and-resources.md`. For command recording and submission, see `command-recording.md`.

---

## What Barriers Actually Do

A barrier has exactly two jobs:

| Job | What it does | What it does NOT do |
|-----|-------------|---------------------|
| **Execution dependency** | Ensures producer stage finishes before consumer stage begins | Does not flush VRAM |
| **Cache management** | Flushes/invalidates tiny non-coherent per-CU caches (L0$, K$) | Does not cause VRAM traffic on modern hardware |

The common mental model — "barriers flush memory to VRAM" — was accurate for AMD GCN (2012) but is wrong for RDNA (2019) and later. On modern hardware, a barrier is cheap: it waits for outstanding L0$/K$ writes to propagate to the coherent L2$, then proceeds.

---

## Hardware Context: Why Barriers Evolved This Way

Understanding the hardware explains why the API looks the way it does.

### AMD GCN (2012) — the original problem

| Component | Cache behavior | Consequence |
|-----------|---------------|-------------|
| ROPs (pixel blending) | Non-coherent write cache wired **directly to VRAM**, bypassing L2$ | Render target writes were invisible to texture samplers until explicitly flushed |
| Command processor | NOT an L2$ client | Indirect draw args written by compute were invisible until L2$ was invalidated |
| Texture samplers | Read through L2$ | Needed L2$ invalidate after any ROP write |
| DCC (delta color compression) | Compressed data in VRAM | Required a decompress pass before sampling |

**Sampling a render target on GCN required**:
1. Wait for ROPs to finish
2. Flush ROP cache → VRAM
3. Invalidate L2$
4. (Optional) DCC decompress pass via compute
5. Now visible to texture samplers

This is why Vulkan 1.0 needed explicit image layout transitions and per-resource barrier lists — the API was modeling real hardware state.

### AMD RDNA (2019) — what changed

| Component | Cache behavior | Consequence |
|-----------|---------------|-------------|
| ROPs | L2$ client — writes go through L2$ | No ROP→VRAM flush needed |
| Command processor | L2$ client | Indirect args visible immediately after L2$ coherence |
| L0$ (per-CU texture cache) | Non-coherent, tiny | Flushes automatically to L2$ on any barrier — no VRAM traffic |
| K$ (scalar/uniform cache) | Non-coherent, tiny | Same as L0$ |
| DCC decompressor | Sits between L2$ and L0$ | No decompress-to-VRAM needed; decompresses on read |

**A barrier on RDNA only needs to**: wait for outstanding L0$/K$ writes to propagate to L2$. No VRAM traffic. Cheap.

### Industry direction

`VK_KHR_unified_image_layouts` (2025) makes image layout transitions optional in most cases — `VK_IMAGE_LAYOUT_GENERAL` is now guaranteed as efficient as specialized layouts, so applications no longer need per-resource layout transitions for performance. Transitions are still required for presentation (`VK_IMAGE_LAYOUT_PRESENT_SRC_KHR`) and a few other cases. Per-resource barrier lists are legacy overhead; the extension requires explicit opt-in (`VkPhysicalDeviceUnifiedImageLayoutsFeaturesKHR.unifiedImageLayouts`).

---

## Stage-Based Barrier Model

The modern model: describe *what happened* and *what needs it*. No resource lists.

```cpp
// Signature:
gpuBarrier(commandBuffer, srcStage, dstStage, hazards = 0);

// Compute writes results → compute reads them as input
gpuBarrier(commandBuffer, STAGE_COMPUTE, STAGE_COMPUTE);

// CPU/GPU writes new descriptors → shader reads them
gpuBarrier(commandBuffer, STAGE_COMPUTE, STAGE_COMPUTE, HAZARD_DESCRIPTORS);

// Rasterizer outputs color/depth → next pass samples them
// STAGE_RASTER_COLOR_OUT auto-flushes ROP caches when needed
gpuBarrier(commandBuffer, STAGE_RASTER_COLOR_OUT | STAGE_RASTER_DEPTH_OUT, STAGE_PIXEL_SHADER);

// Compute writes indirect draw/dispatch args → command processor reads them
// HAZARD_DRAW_ARGUMENTS stalls the CP prefetcher
gpuBarrier(commandBuffer, STAGE_COMPUTE, STAGE_COMPUTE, HAZARD_DRAW_ARGUMENTS);

// Transfer (copy/clear) → compute reads result
gpuBarrier(commandBuffer, STAGE_TRANSFER, STAGE_COMPUTE);
```

### Stages Reference

| Stage | What it represents |
|-------|-------------------|
| `STAGE_TRANSFER` | Copy, clear, blit commands |
| `STAGE_COMPUTE` | Compute dispatch |
| `STAGE_VERTEX_SHADER` | Vertex and mesh shader stages |
| `STAGE_PIXEL_SHADER` / `STAGE_FRAGMENT_SHADER` | Pixel/fragment shader |
| `STAGE_RASTER_COLOR_OUT` | ROP write (render target blending/output) |
| `STAGE_RASTER_DEPTH_OUT` | Depth-stencil write |
| `STAGE_BUILD_BVH` | Ray tracing BVH construction |
| `STAGE_ALL` | All stages — coarse but safe |

Stages can be OR'd together: `STAGE_RASTER_COLOR_OUT | STAGE_RASTER_DEPTH_OUT` means "after both color and depth output finish."

### Odin API

```odin
cmd_barrier :: proc(cmd_buf: Command_Buffer, before: Stage, after: Stage, hazards: Hazard_Flags = {})

Stage :: enum {
    Transfer      = 0,
    Compute,
    Raster_Color_Out,
    Raster_Depth_Out,
    Fragment_Shader,
    Vertex_Shader,
    Build_BVH,
    All,
}
```

> **API sidebar**
>
> | Concept | Vulkan | DX12 | Metal |
> |---------|--------|------|-------|
> | Stage-based barrier | `vkCmdPipelineBarrier2` (`VK_KHR_synchronization2`, core 1.3) with `VkDependencyInfo`; 64-bit `VkPipelineStageFlags2` | `D3D12_RESOURCE_BARRIER_TYPE_TRANSITION` (legacy) or Enhanced Barriers `D3D12_BARRIER_TYPE_GLOBAL` with `SyncBefore`/`SyncAfter` (Agility SDK 1.7+) | `MTLComputeCommandEncoder.memoryBarrier(scope:)` |
> | Image layout transitions | `VkImageMemoryBarrier2.oldLayout/newLayout` (optional with `VK_KHR_unified_image_layouts`; still required for `PRESENT_SRC_KHR`) | No layout concept — resource state tracked via `D3D12_RESOURCE_STATES` | No layout concept |
> | Per-resource lists | Required in Vulkan 1.0–1.2; optional with `VK_KHR_synchronization2` + unified layouts | Required (`D3D12_RESOURCE_TRANSITION_BARRIER`) | Not required — Metal uses coarse barriers + `MTLFence` |

---

## Hazard Flags

Hazard flags handle the small set of cases where a plain stage barrier is insufficient.

| Flag | When required | What it does |
|------|--------------|--------------|
| `HAZARD_DRAW_ARGUMENTS` | After GPU writes draw/dispatch args or vertex/index buffers, before `vkCmdDrawIndirect` / `ExecuteIndirect` / draw call | Stalls command-processor and IA prefetch; without it, CP/IA reads stale data from its prefetch buffer |
| `HAZARD_DESCRIPTORS` | After CPU or GPU writes to descriptor heap/bindless table | Invalidates the sampler's tiny internal descriptor cache |
| `HAZARD_DEPTH_STENCIL` | After depth/stencil read → render target write on the same attachment | Flushes HiZ / early-Z rejection cache |
| `HAZARD_BVHs` | After BVH build, before ray tracing dispatch | Ensures BVH structure is visible to ray traversal hardware |
| *(none)* | After compute writes, before next compute reads | Stage barrier still required; no extra hazard flag — normal L0$/L2$ coherence handles the rest |

**Rule**: start with no hazard flags. Add `HAZARD_DRAW_ARGUMENTS` when writing indirect args, `HAZARD_DESCRIPTORS` when updating bindless tables, `HAZARD_DEPTH_STENCIL` when reusing a depth attachment.

### Odin API

```odin
Hazard :: enum { Draw_Arguments = 0, Descriptors, Depth_Stencil, BVHs }
Hazard_Flags :: bit_set[Hazard]

// Example: indirect dispatch after compute writes the argument buffer
gpu.cmd_barrier(cmd_buf, .Compute, .Compute, {.Draw_Arguments})
gpu.cmd_dispatch_indirect(cmd_buf, arg_buffer, 0)
```

> **API sidebar**
>
> | Hazard concept | Vulkan | DX12 | Metal |
> |----------------|--------|------|-------|
> | Indirect args | `VK_ACCESS_2_INDIRECT_COMMAND_READ_BIT` in `dstAccessMask` | `D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT` transition | `MTLIndirectCommandBuffer` — no explicit barrier needed |
> | Descriptor update | `VK_ACCESS_2_DESCRIPTOR_BUFFER_READ_BIT_EXT` | Descriptor heap writes are CPU-visible; GPU reads after next submit | Argument buffers — no explicit barrier |
> | Depth/HiZ | `VK_ACCESS_2_DEPTH_STENCIL_ATTACHMENT_READ_BIT` + layout transition | `D3D12_RESOURCE_STATE_DEPTH_READ` → `D3D12_RESOURCE_STATE_DEPTH_WRITE` | `MTLFence` between render passes |

---

## Split Barriers

A full barrier drains the GPU pipeline: the consumer stage stalls until the producer finishes. A split barrier separates the signal (emitted after the producer) from the wait (inserted before the consumer), letting independent work fill the gap.

```
Full barrier:
  [producer]──barrier──[consumer]
              ↑ pipeline stall

Split barrier:
  [producer]──signal──[independent work]──wait──[consumer]
                       ↑ GPU stays busy
```

### Single producer

```cpp
// Signal: emit after producer stage finishes
// SIGNAL_ATOMIC_MAX: counter = max(counter, value) — idempotent, correct for ONE producer only.
// For multiple producers, use SIGNAL_ATOMIC_OR with the bitmask pattern below.
gpuSignalAfter(commandBuffer, STAGE_RASTER_COLOR_OUT, counterPtr, counter, SIGNAL_ATOMIC_MAX);

// Independent work that doesn't need the render target result.
// WARNING: this work must NOT read from or write to any resource the producer wrote
// and the consumer will read. If it does, insert a separate full barrier for that resource.
gpuDispatch(commandBuffer, cullingData.gpu, uvec3(1024, 1, 1));

// Wait: stall consumer until signal value is met
gpuWaitBefore(commandBuffer, STAGE_PIXEL_SHADER, counterPtr, counter++, OP_GREATER_EQUAL);
```

### Multiple producers (bitmask pattern)

```cpp
// Each producer sets its own bit
gpuSignalAfter(cmd, STAGE_COMPUTE, counterPtr, 1 << producerA, SIGNAL_ATOMIC_OR);
gpuSignalAfter(cmd, STAGE_COMPUTE, counterPtr, 1 << producerB, SIGNAL_ATOMIC_OR);

// Consumer waits until both bits are set
uint32 bothBits = (1 << producerA) | (1 << producerB);
gpuWaitBefore(cmd, STAGE_COMPUTE, counterPtr, bothBits,
              OP_GREATER_EQUAL, /*mask*/ bothBits);
```

**When to use split barriers**: any time there is independent work (culling, BVH build, other passes) that can execute between the producer and consumer. The GPU scheduler fills the gap automatically; you just need to express the dependency correctly.

> **API sidebar**
>
> | Concept | Vulkan | DX12 | Metal |
> |---------|--------|------|-------|
> | Split barrier signal | `vkCmdSetEvent2` (after producer) | `ID3D12CommandQueue::Signal` (fence) | `MTLCommandBuffer.encodeSignalEvent(_:value:)` |
> | Split barrier wait | `vkCmdWaitEvents2` (before consumer) | `ID3D12CommandQueue::Wait` (GPU-side) | `MTLCommandBuffer.encodeWaitForEvent(_:value:)` |
> | Intra-encoder fine-grained | `VkEvent` | `ID3D12Fence` with `SetEventOnCompletion` | `MTLFence` (intra-encoder resource tracking) |

---

## Timeline Semaphores

The old model allocated one fence object per submit and required manual N-buffering bookkeeping. Timeline semaphores replace this with a single monotonically increasing counter.

### Frame pacing with a timeline semaphore

```cpp
GpuSemaphore frameSemaphore = gpuCreateSemaphore(0);  // initial value = 0
uint64 nextFrame = 1;

while (running) {
    // Wait for the frame that's FRAMES_IN_FLIGHT ago to complete.
    // Frame N can't start until frame (N - FRAMES_IN_FLIGHT) has signaled.
    if (nextFrame > FRAMES_IN_FLIGHT) {
        gpuWaitSemaphore(frameSemaphore, nextFrame - FRAMES_IN_FLIGHT);
    }

    // Record and submit frame nextFrame
    GpuCommandBuffer cmdBuf = gpuStartCommandRecording(queue);
    // ... record draw calls, dispatches, barriers ...
    gpuSubmit(queue, {cmdBuf}, frameSemaphore, nextFrame++);
}

gpuWaitSemaphore(frameSemaphore, nextFrame - 1);  // drain before shutdown
gpuDestroySemaphore(frameSemaphore);
```

### Odin frame loop

```odin
Frames_In_Flight :: 3

frame_sem := gpu.semaphore_create(0)
next_frame := u64(1)

for !should_quit {
    if next_frame > Frames_In_Flight {
        gpu.semaphore_wait(frame_sem, next_frame - Frames_In_Flight)
    }

    // Reclaim frame-arena memory now that the GPU is done with this slot
    frame_arena := &frame_arenas[next_frame % Frames_In_Flight]
    gpu.arena_free_all(frame_arena)

    cmd_buf := gpu.commands_begin(.Main)
    // ... record frame ...
    gpu.cmd_add_signal_semaphore(cmd_buf, frame_sem, next_frame)
    gpu.queue_submit(.Main, {cmd_buf})
    next_frame += 1
}

gpu.wait_idle()  // or: gpu.semaphore_wait(frame_sem, next_frame - 1) for explicit drain
// On multi-queue setups, drain each queue's semaphore before destroying shared resources.
```

### Why timeline semaphores beat per-submit fences

| Capability | Per-submit fences | Timeline semaphore |
|------------|------------------|--------------------|
| Allocation | One fence object per submit | One semaphore, reused forever |
| CPU fast-forward | Must track which fence to wait on | `gpuSemaphoreGetValue(sem)` → last completed frame number |
| Cross-queue sync | Separate fence per queue pair | Queue B waits on queue A's semaphore value directly |
| Frame-arena reclaim | Must map fence → arena slot | `nextFrame % FRAMES_IN_FLIGHT` indexes the slot |
| Query completed work | `vkGetFenceStatus` per fence | Single `vkGetSemaphoreCounterValue` call |

### Odin API

```odin
semaphore_create    :: proc(init_value: u64 = 0, name := "") -> Semaphore
semaphore_get_value :: proc(sem: Semaphore) -> u64
semaphore_wait      :: proc(sem: Semaphore, wait_value: u64)
semaphore_destroy   :: proc(sem: Semaphore)

// Attach signal/wait to a command buffer before submission
cmd_add_signal_semaphore :: proc(cmd_buf: Command_Buffer, sem: Semaphore, signal_value: u64)
cmd_add_wait_semaphore   :: proc(cmd_buf: Command_Buffer, sem: Semaphore, wait_value: u64)
```

> **API sidebar**
>
> | Operation | Vulkan | DX12 | Metal |
> |-----------|--------|------|-------|
> | Create | `vkCreateSemaphore` with `VkSemaphoreTypeCreateInfo.semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE` (core 1.2) | `ID3D12Device::CreateFence` — DX12 fences are always timeline semantics | `[device newSharedEvent]` (`MTLSharedEvent`) |
> | GPU signal | `VkSubmitInfo2.pSignalSemaphoreInfos[].value` | `ID3D12CommandQueue::Signal(fence, value)` | `[cmdBuf encodeSignalEvent:event value:v]` |
> | GPU wait | `VkSubmitInfo2.pWaitSemaphoreInfos[].value` | `ID3D12CommandQueue::Wait(fence, value)` | `[cmdBuf encodeWaitForEvent:event value:v]` |
> | CPU wait | `vkWaitSemaphores` | `fence->SetEventOnCompletion(v, event)` + `WaitForSingleObject` | `[event notifyListener:block atValue:v]` |
> | CPU signal | `vkSignalSemaphore` | `ID3D12CommandQueue::Signal` (from CPU thread) | `sharedEvent.signaledValue = v` |
> | Query value | `vkGetSemaphoreCounterValue` | `fence->GetCompletedValue()` | `sharedEvent.signaledValue` |

---

## Transient Command Buffers

Vulkan 1.0 designed command buffers for pre-recording and reuse. In practice, almost no application reuses command buffers — scene state changes every frame. The modern pattern: create, record, submit, done.

```cpp
// Per-frame pattern — no pool management, no explicit free:
GpuCommandBuffer cmdBuf = gpuStartCommandRecording(queue);

gpuBarrier(cmdBuf, STAGE_TRANSFER, STAGE_COMPUTE);
gpuDispatch(cmdBuf, computeData.gpu, uvec3(64, 1, 1));
gpuBarrier(cmdBuf, STAGE_COMPUTE, STAGE_RASTER_COLOR_OUT | STAGE_RASTER_DEPTH_OUT);
// ... draw calls ...

gpuSubmit(queue, {cmdBuf});
// cmdBuf is consumed. Do not use again.
// Driver uses a bump allocator; memory is reclaimed after GPU finishes.
```

### Odin API

```odin
commands_begin  :: proc(queue: Queue_Type, name := "") -> Command_Buffer
queue_submit    :: proc(queue: Queue_Type, cmd_bufs: []Command_Buffer)
// No explicit free — bump allocator reclaims after GPU signals completion
```

### Why transient beats reusable

| Concern | Reusable command buffers | Transient command buffers |
|---------|--------------------------|--------------------------|
| Memory management | Pool allocation, explicit reset/free | Bump allocator, automatic reclaim |
| Scene changes | Must re-record or maintain multiple versions | Always fresh — no stale state |
| Driver optimization | Driver must preserve recorded state | Driver can optimize freely |
| API complexity | `VkCommandPool`, `VkCommandBufferResetFlags`, secondary buffers | One call to begin, one to submit |
| Practical reuse rate | Near zero in real applications | N/A — not the goal |

> **API sidebar**
>
> | Concept | Vulkan | DX12 | Metal |
> |---------|--------|------|-------|
> | Allocate | `vkAllocateCommandBuffers` from `VkCommandPool` | `ID3D12Device::CreateCommandAllocator` + `CreateCommandList` | `[commandQueue commandBuffer]` |
> | Begin recording | `vkBeginCommandBuffer` | `commandList->Reset(allocator, pso)` | Implicit — MTLCommandBuffer records immediately |
> | Submit | `vkQueueSubmit2` | `ID3D12CommandQueue::ExecuteCommandLists` | `[cmdBuf commit]` |
> | Transient hint | `VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT` | `CreateCommandAllocator` per frame + `Reset` after GPU done | Default behavior — MTLCommandBuffer is always transient |

---

## Common Bugs — Symptoms → Cause

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Indirect draw reads wrong counts | Missing `HAZARD_DRAW_ARGUMENTS` after compute writes arg buffer | Add `gpuBarrier(cmd, STAGE_COMPUTE, STAGE_COMPUTE, HAZARD_DRAW_ARGUMENTS)` |
| Bindless texture reads stale data | Missing `HAZARD_DESCRIPTORS` after descriptor heap update | Add `HAZARD_DESCRIPTORS` to barrier before the shader dispatch |
| Render target sample shows previous frame | Missing barrier between `STAGE_RASTER_COLOR_OUT` and `STAGE_PIXEL_SHADER` | `gpuBarrier(cmd, STAGE_RASTER_COLOR_OUT, STAGE_PIXEL_SHADER)` |
| Depth test accepts fragments that should be occluded | Reusing depth attachment without `HAZARD_DEPTH_STENCIL` | Add `HAZARD_DEPTH_STENCIL` to flush HiZ cache |
| GPU hangs or TDR on frame N+FRAMES_IN_FLIGHT | Timeline semaphore wait skipped or counter not incremented | Verify `nextFrame - FRAMES_IN_FLIGHT` wait logic; check counter increment |
| Validation error: semaphore signal value not monotonically increasing | Reusing a signal value | Timeline semaphore values must strictly increase; use `nextFrame++` |
| Command buffer use-after-submit crash | Reusing transient command buffer | Never read or write a command buffer after `gpuSubmit` |

---

## What's Not Covered Here

| Topic | Where to look |
|-------|--------------|
| Memory allocation (heaps, pools, suballocation) | `memory-and-resources.md` |
| Render passes and framebuffer attachments | `render-passes.md` |
| Ray tracing BVH build and dispatch | `ray-tracing.md` |
| Multi-queue submission (async compute, transfer queue) | `command-recording.md` |
| Sparse resources and residency | External: Vulkan sparse binding docs |
| Mesh shaders and task shaders | `mesh-shaders.md` |
