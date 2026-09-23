---
name: "physical-ai-systems"
summary: "Data pipelines, inference patterns, and training optimization for AI systems operating in the physical world"
type: "design"
description: "Consult this skill when building ML systems for physical-world domains — autonomous vehicles, robotics, satellite/geospatial, IoT fleets, or any system where sensor data (video, lidar, radar, IMU, CAN) must flow from collection through curation, annotation, training, and deployment. Also trigger when designing write-once-run-anywhere inference (online/batch/edge from one pipeline definition), optimizing training throughput on fixed GPU budgets, serving large vision/world models at petabyte scale, or reasoning about spatial intelligence limitations of current vision models. NOT for pure-software agent orchestration (see agent-architecture) or general ML training recipes without a physical-world sensor component."
---

# Physical AI Systems

**The bottleneck in physical AI is never the model — it is the data lifecycle that feeds it.**

Sensor data is multimodal, petabyte-scale, write-optimized, and domain-specific. Every stage from collection to deployment has failure modes invisible to pure-software ML.

---

## Symptom Table

| Symptom | Section |
|---|---|
| GPU utilization is high but training runs are slow | §3 — Throughput > Utilization |
| Same ML pipeline reimplemented for online and batch | §2 — Write-Once Inference |
| Annotation quality drifts across labeling campaigns | §1 — Annotation lifecycle |
| Model works in simulation, fails on real sensor data | §5 — Sim-to-Real Transfer |
| VLM confidently wrong on spatial/counting questions | §6 — Spatial Reasoning Limits |
| Model serving startup takes 10+ minutes per replica | §4 — Serving at Scale |
| Data pipeline stalls on large point clouds or video | §1 — Sensor Data Patterns |

---

## §1 Physical AI Data Lifecycle

### The pipeline: collect → curate → annotate → train → validate

Every physical AI system follows this sequence. The speed of the full cycle — not any single stage — determines model iteration velocity. Encord reports 60% faster iteration cycles when all stages run on a unified platform.

### Sensor data patterns

Physical AI ingests multimodal sensor streams that share no common format:

| Modality | Characteristics | Pipeline concern |
|---|---|---|
| Camera (RGB) | High bandwidth, temporal | Frame extraction, temporal alignment |
| Lidar point clouds | Sparse 3D, large per-frame | Serialization cost, memory pressure |
| Radar | Lower resolution, weather-robust | Fusion alignment with camera/lidar |
| IMU / CAN bus | High-frequency time series | Temporal sync with visual streams |
| Satellite multispectral | 15+ bands, 5-day revisit, stable orbits | N-dimensional data cubes, not RGB |
| Teleoperation recordings | Video + proprioceptive state + commanded actions | Hierarchical: video > wearable > teleop |

**Key insight from Xoople**: satellite pixels on stable orbits act as slow IoT sensors — same location, same conditions, every N days. Treat temporal pixel stacks as time series, not independent images.

**Key insight from Mimic**: robot training data forms a pyramid — massive internet video at the base (diversity), wearable/glove data in the middle (hardware-aligned without robots), teleop data at the tip (most aligned, least scalable). Video action models get 10x sample efficiency on action data by pre-training on video.

### Curation at scale

Finding the needle in petabyte haystacks requires:
- **Embedding-based search**: vectorize sensor data, enable semantic retrieval (Samsara's visual search — embed video frames, similarity-search against text prompts)
- **Long-tail event mining**: most driving miles are boring; the rare events (near-misses, edge cases) are what matter for training
- **Active learning**: select data to label based on model uncertainty, not random sampling

### Annotation lifecycle

The progression: fully manual → model-assisted → model-led with human QA.

- **Pre-labeling**: run VLMs or detection models over raw data before human annotators touch it
- **Automated for repeatable tasks**: pick-and-place seen thousands of times can be auto-labeled
- **Human-in-the-loop for subjective tasks**: evaluation quality, chatbot tone, safety-critical edge cases
- **Quality tracking**: compare inter-annotator agreement, use sown test tasks to measure annotator accuracy, track label acceptance rates over time

**Annotation is the moat.** The model is commoditized; the labeled data is not.

---

## §2 Write-Once-Run-Anywhere Inference

Physical AI products operate on two tempos that share identical ML logic:

| Tempo | Latency | Example |
|---|---|---|
| **Real-time** | Seconds | Driver alert from dash cam |
| **Batch** | Hours | Re-process all fleet video with updated model |
| **Edge** | Milliseconds | On-device inference in robot or vehicle |

### The Cascade pattern (Samsara)

Separate pipeline *definition* from pipeline *execution*:

1. **Logical plan**: define pre-process → infer → post-process as a DAG of stages
2. **Compilation targets**: compile the same logical plan to Ray Serve (online), Ray Data (batch), or Spark (batch)
3. **Source/sink abstraction**: HTTP request/response for online; S3/Parquet for batch
4. **Per-stage resource binding**: CPU for pre-processing, GPU for inference — each stage scales independently

**Result**: decoupling CPU pre-processing from GPU inference with the same total machines increased GPU utilization from 19% to 55% (2.9x) — without changing the model.

### Pipeline composition patterns

- **Fan-out**: one input produces multiple items to process (e.g., detected objects each need post-processing)
- **Fan-in**: aggregate results from parallel branches
- **Filter**: conditional execution based on prediction threshold
- **Merge**: combine branches back into a single stream

### Back-pressure

Cascade piggybacks on Ray Serve's existing mechanisms (`max_ongoing_requests`, `target_requests`). No custom back-pressure layer needed — use the runtime's native flow control.

---

## §3 Throughput > Utilization

**Optimize for wall-clock throughput, not GPU utilization.** Latitude AI found concrete cases where high GPU utilization correlated with 2x slower training. The metric that matters: time from experiment start to experiment end, including setup and teardown.

### Finding the bottleneck

A training pipeline has three stages with buffers between them:

```
[Load/Preprocess] → split_operator → [Transfer] → prefetch_queue → [Train]
```

Diagnose by observing buffer depths:

| Split operator | Prefetch queue | Bottleneck is... |
|---|---|---|
| Empty | Empty | Load (data pipeline starved) |
| Full | Empty | Transfer (network, serialization) |
| Full | Full | Train (model compute) |

**The bottleneck moves.** It shifts within a single run (ramp-up vs steady state) and across runs (when someone bumps image resolution or adds model layers). Continuous monitoring is required, not one-time profiling.

### The Run Tracker pattern

Monitor every run continuously, not by comparing against baselines:
- **Throughput curve shape**: fast ramp-up + steady state + clean ramp-down = healthy; slow ramp-up + fluctuation = autoscaler thrashing; mid-run sag = straggler or system instability
- **Queue depth at each buffer**: identifies which stage is starved or saturated
- **Async actor profiling**: any actor profiles itself in the background for a few steps, uploads py-spy flamegraphs or torch profiler traces — zero friction, production-safe
- **Fleet dashboards**: plot throughput across all active runs; alert when a run falls below baseline speed
- **Nightly regression**: run a control job per workstream, regress throughput against baseline, detect regressions before they compound

**Outcome**: ML engineers found 2–5x throughput gains by self-diagnosing bottlenecks. Optimization burden shared between ML and infra teams.

---

## §4 Serving VLMs and World Models at Scale

At petabyte scale, throughput is the governing metric for model serving — delays in one workload cascade across a shared on-prem cluster.

### Minimize replica startup latency

Model replica startup can dominate autoscaling cost. Hyundai's breakdown for Cosmos world models:

| Phase | Optimization |
|---|---|
| Container image pull | Pre-cache images on nodes; use pod affinity or DaemonSet-based preloading |
| Model weight loading | Prefetch SafeTensor files into page cache (sidecar container or RunAI Model Streamer) |
| Torch compilation | Persist and share `VLLM_CACHE_ROOT` across replicas — eliminates largest latency contributor |

RunAI Model Streamer benefit scales with tensor parallelism: ~2x for TP1, ~5x for TP2/TP4 (parallelized, coordinated NFS reads vs fragmented default loader).

### Configuration complexity

No single parallelism config works for every workload. Profile real workloads first, then design serving:
- **HSDP** (hybrid sharded data parallelism): reduces per-GPU memory, combinable with compute parallelism
- **CFG parallelism**: concurrent conditional/unconditional branches for diffusion models
- **USP** (Ulysses Sequence Parallelism): splits long sequences across GPUs
- **DLO** (distributed layer-wise offloading): streams layers from CPU memory as needed

**Counterintuitive finding**: the fastest per-request config (HSDP+CFG+USP) is not always highest throughput. Eight independent single-GPU DLO instances beat multi-GPU gang scheduling on throughput because: (a) no synchronization overhead, (b) single-GPU failure affects only one pod, and (c) Kubernetes reschedules small pods faster.

### Fault tolerance principle

On on-prem clusters, failures happen everywhere — GPUs, PCIe, networking, cooling. Prefer smaller independent workers over large multi-GPU gangs. A GPU failure in a gang slows the entire group; in independent workers, it affects one pod.

---

## §5 Simulation-to-Real Transfer

### Video action models (Mimic)

The thesis: scaling video prediction quality maps directly to action prediction quality.

- **Oracle experiment**: when a model is given ground-truth future video, its action decoder produces near-perfect actions. This proves the action decoder attends heavily to predicted video — better video = better actions.
- **Architecture**: video model backbone (e.g., Flux 3) replaces the VLM backbone of traditional VLAs. Language + video stream feeds an action decoder (MMD-style architecture).
- **Sample efficiency**: 12% of action data matches 100% performance when video backbone is pre-trained at scale.
- **In-context learning**: video backbones naturally support video prompting — show a human performing the task, robot executes it.

### Inference on the robot

- Target ~100ms latency (human reaction speed) via quantization, compilation, partial video denoising
- Zero-copy IPC between model and robot control (18,000x latency reduction)
- Currently local (RTX 5090 on-robot); future possibility of low-latency server inference via Ray Serve

### Geospatial sim-to-real (Xoople)

- **Temporal embeddings** (TERRA model): collapse 40 timestamps × 17 bands into per-pixel embeddings — a fingerprint of that location over time
- **Downstream reuse**: one embedding pass enables multiple fine-tuned tasks (change detection, coastal erosion, vegetation health) without re-processing raw data
- **Scaling**: 40,000 km² at 60 timestamps in 40 minutes on 12 A10 + 8 A100 GPUs via Ray Data streaming

---

## §6 Spatial Reasoning Limits of Current Vision Models

Current frontier models fail at fundamental visual tasks that physical AI requires:

| Capability | Example failure | Why it fails |
|---|---|---|
| Counting | "How many rails?" → model says 2, answer is 37 | No spatial grounding in reasoning |
| Depth perception | "What is the gripper closest to?" → wrong object | Pixel-to-text mapping loses 3D info |
| Temporal tracking | "How many passes?" → 6, answer is 16 | Video frames processed without temporal coherence |
| Metric spatial reasoning | "How many cm between objects?" | Benchmarks test left/right, not metric distances |

### Root cause

Models map image → text → chain-of-thought. The image-to-text projection loses spatial information. Reasoning in text space becomes ungrounded — the chain of thought drifts from the input, producing confident hallucinations.

### Visual thinking direction (Elorian AI)

- **Interleaved image-text reasoning**: model generates annotated images as intermediate reasoning steps (e.g., circling each counted object), feeding them back as input
- **Verifiable visual data**: visual problems enable synthetic dataset creation with ground-truth answers
- **Smaller models, targeted capacity**: by not trading off against coding/multilingual capabilities, visual-specialist models outperform larger generalist models on spatial tasks

### Scaling is not the solution

Scaling compute/data has not closed the visual reasoning gap. Claude outscales Gemini in compute but underperforms on visual tasks. The right training objective for vision (analogous to next-token prediction for language) remains an open problem — next-frame, next-pixel, next-scene prediction have all been tried without equivalent scaling behavior.

### Implication for physical AI

Any system relying on VLMs for spatial reasoning (robot planning, AV scene understanding, satellite analysis) must design around these limitations: use structured sensor fusion rather than asking a VLM to reason about 3D space from 2D pixels alone.

---

## Platform Architecture Patterns

### Contract-based governance (Hyundai)

Helm chart = contract. Platform-managed templates enforce policy (upgrades, storage, networking, autoscaling). User-managed `values.yaml` configures workloads. GitOps via Argo CD with webhook sync, restart hashes for cluster recreation, `ignoreDifferences` for KubeRay-managed fields.

### Agent integration

Platform users are increasingly agents. Safe integration: single source of truth for human intent (Jira), agent skills for workflows (cannot enforce policy), MCP servers as controlled boundaries exposing only approved tools/scopes.

---

## References

| Reference | When to read |
|---|---|
| `references/ray-summit-2026-physical-ai-patterns.md` | Detailed patterns from 7 Ray Summit 2026 talks: Cascade internals, Hyundai serving configs, Latitude throughput tracking, Xoople geospatial pipeline, Mimic video action models, Elorian visual thinking, Encord annotation lifecycle |
