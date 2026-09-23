# Ray Summit 2026 — Physical AI Patterns

*Synthesized from 7 talks at Ray Summit 2026. Each section traces back to a specific talk.*

---

## Encord: Multimodal Annotation Pipelines

*Source: [Agents and Robots: The Human Effort Putting AI Into Production](https://www.youtube.com/watch?v=f5TYdiw4-lE)*

### Core problem

Both agentic AI and robotics generate messy multimodal logs that need human context to become training data. The data lifecycle — curate → annotate → evaluate — is the bottleneck, not the model.

### Annotation pipeline architecture

1. **Data ingestion**: integrate directly with cloud storage, stream sensor data (lidar, depth imagery, UMI teleoperation, video time series) into the platform
2. **Search and filtering**: embedding-based search at petabyte scale to find long-tail events and interesting logs
3. **Model-led pre-labeling**: run InVideo, OpenAI, Anthropic models across data before human annotation — provides temporal context, cross-modality labels
4. **AI-accelerated human annotation**: humans review and correct model labels rather than starting from scratch
5. **Quality management**: inter-annotator comparison, per-annotator accuracy metrics, sown test tasks, label acceptance tracking over time

### Key metrics

- 60% faster model iteration cycle from unified platform
- Reduced annotation task volume while improving model mAP
- Repeatable tasks (e.g., well-represented pick-and-place) can be fully automated; subjective or evaluation tasks require human QA loops

### Design principle

"Annotation is the moat." Model architectures are converging; labeled data quality and the speed of the label-train-evaluate loop differentiate production systems.

---

## Samsara: Cascade Write-Once Inference

*Source: [Cascade: Write-Once Run-Anywhere Inference on Ray](https://www.youtube.com/watch?v=3s5etTGANrc)*

### Operating context

Samsara operates millions of AI dash cams processing 180 billion minutes of video annually across 99% of US roads. Products like Visual Search require identical ML logic running in both real-time (query vectorization + similarity search) and batch (index all new video).

### Cascade architecture

**Logical plan**: a pipeline of stages (pre-process → infer → post-process) defined once in Python. Each stage is a function or model class.

**Compilation targets**: the same logical plan compiles to different Ray primitives:

| Concept | Ray Serve (online) | Ray Data (batch) | Spark (batch) |
|---|---|---|---|
| Source/Sink | HTTP request/response | DataFrame / S3 | DataFrame / S3 |
| Map/Infer | Deployments | DataFrame map functions | DataFrame map functions |
| Scaling unit | Replicas | Actor pools | Spark executors |

**Per-stage resource binding**: `ray.actor.options` specifies CPU/GPU per stage. Autoscaling uses Ray Serve replicas (online) or Ray Data actor pools (batch).

**Configuration-as-code**: single YAML defines pipeline name, stages with resource specs, and compilation targets with source/sink bindings.

### Observability

- End-to-end distributed tracing: one trace per request across all stages
- Per-stage span timing reveals where time is spent (queuing vs computation)
- Example: 42s total request — 27s queuing at pre-process, 13s queuing at inference, actual computation much less

### Decoupled scaling results

Same total machines, coupled vs decoupled:
- **Coupled** (CPU+GPU in same replica): GPU utilization ~19% — GPUs idle while CPUs are busy
- **Decoupled** (independent CPU/GPU scaling): GPU utilization ~55% — 2.9x improvement
- No model changes required — purely execution architecture

### Back-pressure

Inherits Ray Serve settings: `max_ongoing_requests`, `target_requests`. No custom layer.

---

## Hyundai: Physical AI Data Platform at Petabyte Scale

*Source: [Operating a Production-Scale Physical AI Data Platform with Ray](https://www.youtube.com/watch?v=AdlcL8bPZk8)*

### Platform evolution

**Before Ray**: Airflow + Triton Inference Server. Limitations: request/response interface mismatch with batch code, communication overhead transferring large sensor data between services, tightly coupled compute and model management.

**After Ray**: Airflow orchestrates workflows, Ray handles all distributed compute (CPU + GPU), MLflow manages model lifecycle. Users validate locally then scale via Ray Jobs API. KubeRay provides autoscaling, rolling updates, observability.

### Hard-won lessons

1. **GPU task reuse trap**: when `num_gpus` is in the `@ray.remote` decorator, `max_calls=1` (worker exits after one task). When GPU resources are assigned via `.options()` at invocation time, that default may not apply — worker reuse retains CUDA state, causing memory leaks.
2. **Async actor design**: actors processing different sensor streams that occasionally synchronize can deadlock if sync methods aren't async-aware. One actor's long operation blocks another's synchronization call, stalling the pipeline.
3. **Observability reveals bottlenecks**: NVIDIA Nsight Systems profiling via Ray Train revealed heavy GPU-to-GPU communication from SyncBatchNorm. Enabling GPU Direct RDMA over InfiniBand restored near-linear scaling.

### VLM/World Model Serving

**Replica startup optimization** (Cosmos world models):

| Technique | Effect |
|---|---|
| Node-cached container images (pod affinity / DaemonSet preloading) | Eliminates image pull latency |
| SafeTensor prefetch into page cache (sidecar or RunAI Model Streamer) | 2x faster for TP1, 5x for TP2+ |
| Shared torch compilation cache (`VLLM_CACHE_ROOT` on persistent storage) | Eliminates largest startup contributor |

**Parallelism configuration** (Cosmos Tokenizer — image-to-video):

Tested on 8×H100 with NVSwitch:
- HSDP + CFG + USP: lowest per-request latency
- 8× independent single-GPU DLO: highest throughput (no sync overhead, better fault isolation)

**Fault tolerance principle**: prefer single-GPU worker pods. In multi-GPU gangs, one failed/throttled GPU slows the entire group. Single-GPU pods: Kubernetes reschedules faster, failure blast radius is one pod.

### GitOps platform contract

- Helm chart = contract between platform team and users
- Platform-managed templates enforce policy (upgrades, storage, networking, autoscaling)
- User-managed `values.yaml` configures workloads
- Argo CD webhook sync minimizes deploy delay; restart hashes trigger cluster recreation on config change
- `ignoreDifferences` prevents Argo CD / KubeRay operator conflicts on operator-managed fields (replicas, scale strategy)

### Agent integration pattern

- User agent automates deployment via Ray Deployment skill → updates `values.yaml` → creates PR
- Platform admin agent reviews against Jira-recorded agreements before merge
- Kubernetes MCP server exposes only approved cluster info (status, logs) to agents
- Ray Debugging skill collects K8s logs + Ray status + metrics for agent-assisted diagnosis

---

## Latitude AI: Throughput Optimization Patterns

*Source: [Performant Training for All Workstreams](https://www.youtube.com/watch?v=oyUbrX8ZF54)*

### Context

Latitude AI (Ford subsidiary) ships perception models for autonomous driving. Fixed on-prem GPU cluster, ~2,000 experiments/week, 40-50 engineers, jobs ranging hours to weeks. Multimodal data: lidar, cameras, radar point clouds.

### Why throughput, not utilization

Infrastructure noise (filesystem outages, network blips) makes baseline comparisons unreliable. Model code changes constantly. The one stable metric: **wall-clock throughput** — samples processed per unit time from start to finish, including setup and teardown.

Concrete counterexample: achieved high GPU utilization but the training run was 2x slower (GPU was busy with inefficient work).

### Bottleneck diagnosis via buffer depth

Three-stage pipeline: Load → Transfer → Train, with buffers (split operator, prefetch queue) between them.

| Split operator depth | Prefetch queue depth | Bottleneck |
|---|---|---|
| Empty | Empty | Load (data pipeline starved) |
| Full | Empty | Transfer (network, serialization, shuttling large tensors) |
| Full | Full | Train (model is the bottleneck — ideal if all queues are fed) |

### Run Tracker

- **Live throughput view**: healthy = fast ramp + steady state + clean ramp-down; unhealthy = slow ramp (autoscaler thrashing), mid-run sag (straggler GPU, system instability)
- **Queue depth view**: tracks buffer levels at each stage boundary throughout the run
- **Async actor profiler pattern**: a separate actor profiles target actors for a few steps in the background, uploads flamegraphs/torch traces. Separate process avoids profiling overhead contaminating measurements. 2-3 profiled actors suffice per run. Production-safe.
- **Fleet dashboard**: all active runs in a workstream plotted together — instantly spot slow runs, set alerts against baseline speed
- **Workstream evolution view**: throughput and bottleneck fraction over time per model — track whether data pipeline or training step is primary bottleneck as the model evolves
- **Nightly regression**: control run per workstream, regress throughput against baseline, detect and alert on degradation

### Bottleneck movement

Bottlenecks move both within a run (ramp-up vs steady state) and across commits (bumping resolution shifts bottleneck from train → load; adding model layers shifts load → train). Continuous tracking required.

### Agent optimization loop

Metric store (BigQuery) is queryable by agents: pull throughput + buffer levels → identify limiting stage → examine profiles → propose kernel improvements → launch run → read metrics to verify. Closes the optimization loop without human intervention.

### Practical notes

- Merged all data pipeline stages into a single Ray task to avoid serialization/deserialization overhead and throughput variance between tasks
- Caching viable for some workstreams but not for large point clouds / large images where storage per node is limiting
- Network instability surfaces as throughput fluctuation in the data pipeline view

---

## Xoople: Geospatial ML Pipelines

*Source: [Satellite Imagery to Machine-Readable Intelligence](https://www.youtube.com/watch?v=M9Mkrxm9rdY)*

### Domain characteristics

- 200+ data formats in the geospatial ecosystem, organically grown, write-optimized, poor interoperability
- Sentinel-2: 15+ spectral bands, 5-day revisit cycle, stable orbits → pixels are slow IoT sensors
- Data forms N-dimensional cubes: X × Y × bands × time
- Not RGB — includes infrared, aerosols, radar (Sentinel-1 SAR)

### Data pipeline

1. **Mosaic reconstruction**: satellite captures in strips; overlap may be captured at different times/conditions; clouds/shadows/glare must be resolved to pick best-available pixel
2. **Format**: Zarr (chunked N-dimensional arrays) — parallel read/write by chunk, metadata stores chunk positions for parallelized I/O. Custom Zarr datasource for Ray Data (contributed with Anyscale; alpha available in latest Ray).
3. **Dixel representation**: stack 40 timestamps × 17 bands (Sentinel-1 radar + Sentinel-2 optical) per pixel → temporal fingerprint fed to GPU

### TERRA foundational model

- Temporal Embeddings of Surface Spectra for Health Representation and Analysis (University of Cambridge)
- Input: dixel (pixel time series across bands and timestamps)
- Output: one embedding per pixel for a time range — collapses temporal complexity into a latent fingerprint
- Downstream: fine-tune for multiple tasks (change detection, coastal erosion, vegetation health, fire detection) from same embeddings without re-processing raw data

### Ray Data pipeline architecture

**Driver** (no pixel computation): builds area-of-interest grid, creates Zarr skeleton, hands off to workers, finalizes metadata.

**Workers**:
1. `from_items` → cells (data queue, no data loaded yet)
2. `flat_map` with `read_build_cell` → reads from Zarr, builds dixel representations, splits cells into processable blocks
3. `map` with `InferActor` (stateful — holds model weights) → batch GPU inference
4. `map` with write actor (stateful — holds cloud connection) → writes blocks back to Zarr in parallel (no coordination needed since chunks are deterministic, non-overlapping)

**Key decisions**:
- Object store size capped to prevent raylet from overloading memory with dixel representations
- Avoided `group_by` — requires full shuffle through object store, same memory pressure problem
- Streaming by default — tasks write directly to storage as they complete

### Scale results

- Saxony (Germany): 40,000 km², 60 timestamps → 40 minutes on 12 A10 + 8 A100 GPUs
- Linear scaling with added GPUs; area of interest size is not a bottleneck
- GPU starvation only at pipeline start; 100% utilization during steady state

### Visualization

PCA on high-dimensional embeddings projected to RGB for expert review. Captures typology, seasonal variance (river bank shifts), land use patterns. TERRA captures more temporal variance than spatial-only models (e.g., DINO) due to time-series integration.

---

## Mimic Robotics: Video Action Models

*Source: [Video Action Models](https://www.youtube.com/watch?v=Jsh58sufKXA)*

### Core thesis

The future of robotics models is video generation, not VLM fine-tuning. Video backbones understand dynamics; VLMs understand semantics. Robotics needs dynamics.

### Data pyramid

| Layer | Source | Scale | Hardware alignment |
|---|---|---|---|
| Internet video | YouTube, open datasets | Millions of hours | Low (diverse but not robot-specific) |
| Wearable data | Gloves with wrist cameras + finger joint recordings | Hours–thousands of hours | Medium (visually similar to teleop, no robot needed) |
| Teleop data | Robot teleoperation with proprioceptive state + actions | Hours–hundreds of hours | High (exact hardware, least scalable) |

### Architecture: Video Action Model (VAM)

Traditional VLA: VLM backbone → action decoder (trained on teleop data). Must learn all dynamics from scarce teleop data.

VAM: Video model backbone (Flux 3) → action decoder. Video backbone pre-trained on massive video data already understands dynamics. Action decoder leverages these representations.

**Oracle experiment**: when given ground-truth future video, the action decoder produces perfect actions. This proves: (a) action decoding attends heavily to predicted video, (b) improving video prediction directly improves action prediction.

**Sample efficiency**: 12% of action data produces equivalent success rate to 100% when video backbone is pre-trained. ~10x more sample efficient than VLAs.

### Flux-Mimic collaboration

Black Forest Labs Flux 3 (video/image/audio) + Mimic action decoder. Language + video streams feed through unchanged; action modality added as MMD-style branch optimized for real-time.

### Inference optimization

- Target: ~100ms (human reaction speed)
- Techniques: quantization, torch compilation, partial video denoising, action denoising step-skipping
- At inference: action decoder runs without video generation (noise schedule allows it) — no performance drop
- Zero-copy IPC (mimic IPC): 18,000x latency reduction between model and robot control
- Currently local on RTX 5090; potential future: low-latency server inference via Ray Serve

### Streaming data loader (Ray Data)

**Before** (disk-cached): download all data → segment/preprocess → save to disk → train. Time to first batch: 47+ minutes. Not scalable beyond disk capacity.

**After** (Ray Data streaming): shard episodes to workers → stream and process in-flight → feed to training. Time to first batch: seconds. Arbitrarily large datasets. Fail-fast (errors surface immediately, not after 50 minutes of data prep).

**Trade-offs**: requires idle CPUs for preprocessing; GPU starvation risk if streaming can't keep up; must implement buffered shuffling to maintain batch randomness (not free with streaming).

### In-context learning

Video backbones naturally support video prompting — provide a clip of a human performing the task, robot executes it. Same architecture, no retraining. This is a direct consequence of the video generation paradigm (video context = generation context).

---

## Elorian AI: Spatial Reasoning Limits

*Source: [Why Current AI Cannot Truly See the World](https://www.youtube.com/watch?v=zPyKc7_fbW8)*

### The gap

Vision-dependent physical industries (robotics, engineering, satellite, manufacturing) remain underserved by AI because frontier models don't have visual reasoning at their core. Multimodal is an add-on to language, not a native capability.

### Concrete failures of frontier models

| Task | Correct answer | Frontier model answer | Failure type |
|---|---|---|---|
| Count rails on table | 37 | 2 | Counting / spatial grounding |
| Gripper closest object | Right stove knob | Right stove pan | Depth perception |
| Shell game ball position | Left | Middle | Temporal tracking |
| Ball passes in video | 16 | 6 | Video frame coherence |

### Three paradigms of visual understanding

1. **Generation** (Flux, Veo, Sora): high-quality images/video but no physical grounding — explosions look Hollywood, not real
2. **Understanding** (SAM 3, YOLO, RCNN): consistent pixel→label mapping but passive — can't answer open-world questions, limited to trained categories
3. **Thinking** (frontier): spatial + temporal intelligence extracting actionable information for planning — this is what physical AI needs and what current models fail at

### Root cause: image → text → reasoning loses spatial information

Models project images to text tokens, then reason in text space. The chain of thought becomes increasingly detached from the visual input. Hallucinations emerge because reasoning isn't grounded in pixels.

### Visual thinking approach

- **Interleaved image-text reasoning**: model generates annotated images as intermediate steps (circling objects, drawing on the image), feeds them back as input
- **Verifiable synthetic data**: visual problems have ground-truth answers → can generate training data with guaranteed correctness
- **Capacity targeting**: no need to trade off against coding/multilingual capabilities → smaller models achieve SOTA on visual tasks

### Benchmark problems

- **MMMU Pro**: many questions answerable without looking at the image; extremely leaked
- **ARC-AGI**: 32×32 or 64×64 pixel grids — solving these says nothing about understanding CAD drawings or floor plans
- **New benchmarks needed**: professional-setting tasks (CAD problems, engineering drawings), visual agent benchmarks (ALE — agents' last exam), fundamental spatial reasoning across video frames

### Scaling doesn't fix it

Claude is bigger, trained on more compute and data than Gemini, but worse on visual tasks. The right training objective for vision (analogous to next-token prediction for language) remains unknown. Next-frame, next-pixel, next-scene prediction have all been tried without equivalent scaling behavior.

### Implication

Physical AI systems cannot rely on VLMs for spatial reasoning. Design around the limitation: structured sensor fusion, geometric priors, specialized visual models, and hybrid architectures that don't ask a language model to reason about 3D space from 2D projections.
