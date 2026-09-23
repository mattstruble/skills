---
name: "ray-data-pipelines"
summary: "Design patterns for building production Ray Data pipelines across CPU/GPU heterogeneous clusters"
type: "engineering"
description: "Consult this skill when designing or debugging distributed data processing pipelines on Ray Data. Trigger when choosing between Ray Data vs Ray Core actors vs Spark, tuning CPU/GPU resource ratios, handling fault tolerance for native code (C++/CUDA), sizing blocks and partitions, integrating with storage layers (Parquet/Lance/Iceberg/S3), or diagnosing back-pressure and spilling issues. NOT for Ray Serve inference endpoints, Ray Tune hyperparameter search, or general distributed systems design."
---

# Ray Data Pipelines

**The pipeline shape — not the cluster size — determines GPU utilization.**

Production Ray Data pipelines fail most often from three causes: wrong
stage boundaries, misconfigured buffer sizes, and naive resource allocation.
The patterns below address all three, drawn from 13 production deployments
at Ray Summit 2026.

---

## When to Use Ray Data

| Scenario | Use Ray Data | Use Ray Core Actors | Use Spark/External |
|---|---|---|---|
| Streaming heterogeneous CPU→GPU pipeline | ✅ Primary use case | | |
| Simple fan-out with uniform tasks | | ✅ More control | |
| SQL-heavy joins/aggregations on structured data | | | ✅ Better optimizer |
| Need fractional GPU (0.25) per task | ✅ Native support | | |
| C++ bindings that seg-fault | ✅ With task isolation | ✅ Manual process mgmt | |
| Petabyte video/image processing | ✅ Proven at 600TB+ | | |
| Feature preprocessing for training | ✅ Zero-copy Arrow | | Spark has edge on stats aggregation at extreme scale |

**Key differentiator**: Ray Data pipelines independently scale CPU and GPU
stages through streaming execution. Spark fuses all stages into one resource
type. Ray Core gives full control but requires manual back-pressure,
buffering, and fault handling.

CoreWeave demonstrated this directly: migrating from Ray Core to Ray Data
for a 600TB video captioning pipeline cut GPU time by 25% with zero
application-level fault handling code.

---

## Pipeline Design Patterns

### Pattern 1: Streaming Stage Pipeline
Separate IO-bound, CPU-bound, and GPU-bound work into distinct operators
connected by streaming buffers.

```
Read (IO) → Decode (CPU) → Infer (GPU) → Write (IO)
```

Each stage scales independently. Ray Data's streaming execution overlaps
stages so downstream GPUs process while upstream CPUs decode the next batch.

**When to use**: Stages have different resource profiles and the payload
between stages is small relative to processing time.

### Pattern 2: Fused Actor Pipeline
Combine fetch + decode + inference inside a single actor class, passing
only lightweight metadata between actors and the next stage.

```
FusedActor[fetch→decode→infer] (GPU) → Score/Fuse (CPU)
```

**When to use**: The intermediate payload between stages is large (e.g.,
decoded video frames at ~100MB per clip). Motive found this 2x faster than
the modular approach because it eliminates serialization of heavy payloads
across the object store boundary.

### Pattern 3: Three Heuristics for Where to Cut

Before splitting stages, evaluate three asymmetries (from Motive):

| Question | If YES → split | If NO → fuse |
|---|---|---|
| **Cost asymmetry**: Do stages need different hardware (CPU vs GPU)? | Split | Fuse |
| **Change-frequency asymmetry**: Does one stage change more often? | Split (cache the stable stage) | Fuse |
| **Payload asymmetry**: Is data between stages large (>10MB/item)? | Fuse (avoid serialization) | Split is safe |

Only measurement determines where you *should* cut. The heuristics tell you
where you *could* cut.

### Pattern 4: Medallion Architecture
Layer pipeline outputs as bronze → silver → gold for progressive
refinement with independent rerunning per layer.

HeartFlow's PAL pipeline: bronze ingests raw S3 blobs into Parquet, silver
applies vectorized PyArrow row transforms, gold runs group-by aggregations.
Each layer is a separate Dagster asset backed by Ray Data jobs,
enabling selective re-execution when only downstream logic changes.

### Pattern 5: Disaggregated Data Loading
Offload heavy preprocessing (decode, tokenizer encoding) from training
hosts to a separate Ray-managed compute pool.

Luma AI's Koba/KoJo architecture: training nodes send corpus references to
a disaggregated pool that handles fetch → decode → VAE encode, returning
only compact latents. Result: 17% step-time reduction, 58% peak HBM
savings, and the ability to cache deterministic results across jobs.

---

## CPU/GPU Heterogeneity Management

### Resource Ratio Tuning
The CPU:GPU ratio determines whether GPUs starve or idle.

**Method** (from CoreWeave 1600-GPU pipeline):
1. Start with estimated CPU decode rate and GPU inference rate
2. Set `num_cpus` and `num_gpus` per stage explicitly — Ray Data cannot
   infer optimal ratios automatically
3. Monitor GPU utilization: if <50%, add CPU decode workers
4. CoreWeave went from 10% → 25% → 54% → ~100% GPU utilization by
   iteratively tuning the CPU:GPU ratio

**Starvation looks like satisfaction**: When GPUs aren't explicitly told how
many resources to claim, throughput looks "fine" but GPUs are massively
underutilized. Always specify total GPU/CPU resources explicitly.

### Fractional GPUs
Use `num_gpus=0.25` to pack multiple model replicas per GPU for small
models. Motive fit 4 model replicas on one GPU for lightweight detection
models.

### Dynamic GPU Reallocation
Pinterest's synthetic data pipeline: first-stage generation GPUs sit idle
after completing their work. After 2-3 minutes of idle time, the Ray
controller reallocates them to the scoring stage, effectively doubling
scoring throughput without adding hardware.

---

## Fault Tolerance Patterns

### C++ / Native Code Isolation (Zoox)
Treat native bindings as radioactive — isolate in disposable processes:

1. Wrap C++ calls in a `@ray.remote` task with `max_calls=1` — each
   invocation gets a fresh worker process that dies after completion
2. The parent actor holds a reference and can `ray.kill()` on timeout
3. Use `ray.wait(pending, num_returns=1, timeout=T)` to collect results
   in completion order, not submission order — critical for skewed data
4. Never call `ray.get()` in a loop — this is head-of-line blocking

**Result**: Zoox went from 14h partial completion (300K records, 100 nodes)
to 5h full completion with <2% error rate.

### Pipeline-Level Fault Tolerance
At 1500+ GPUs, failures are guaranteed. Ray Data handles this by:
- Replacing failed inference engine actors automatically
- Keeping redundant nodes (e.g., 1500 of 1600 active, 100 as replacements)
- Zero-stall completion of 600TB pipeline (CoreWeave)

### Checkpoint and Resume
- HeartFlow: Dagster materialization records track which bronze/silver/gold
  assets completed; failed phases restart without re-running the full pipeline
- Luma AI Koba: Deterministic cursor tracking per dataset enables exact
  resume from failure point; state stored in PyTorch state_dict
- Exa: Lance fragment-level completion tracking — diff real state vs
  planned state to identify remaining work without re-scanning

### Failure Tracking (Zoox)
Use a Ray queue actor as a failure sink: mapper actors drop failed records
into the queue and continue processing. A separate reporter thread
periodically consolidates failures into a Parquet file. At job end,
aggregate all shards into one `failure.parquet` with grouped error reasons.

---

## Performance Tuning Checklist

### Block Size
- **Too large**: All blocks progress slowly in parallel; first write appears
  after hours; users can't validate output schema early
- **Too small**: Many tiny output files; downstream listing overhead on S3
- **Heuristic**: Target blocks-per-actor that gives writes within minutes,
  then use `min_rows_per_file` to coalesce small files on output
- No universal formula — run 2-3 calibration jobs on representative data

### Repartitioning
- Repartition once at read time, not between stages (Pinterest learned this:
  inter-stage repartition creates gaps that starve GPUs)
- CoreWeave: initial 150 blocks for 70M videos was too few; repartitioning
  to match available parallelism was the first bottleneck fix
- For skewed data, use default (bin-pack) scheduling, not SPREAD — equal
  task counts ≠ equal load distribution (Zoox)

### Buffer and Memory
- Ray Data v2.60+: per-actor buffer limits replace stage-level back-pressure
- Old design: global resource manager → spilling on GPU nodes with smaller
  object stores → cascading GPU idle time
- New design: each actor gets proportional buffer subdivision of its node's
  object store; actors back-pressure individually → no spilling
- Watch in-flight blocks — they outlive task execution and accumulate

### Batch Size
- GPUs want large batches; CPUs are flexible
- Uber found batch_size is a key knob balancing throughput vs memory
- Use PyArrow batch format with zero-copy for CPU transforms

### Concurrency and Actor Sizing
- Ray Data is moving to actor-only model (deprecating mixed task/actor)
- New sizing policy considers both input AND output buffer fullness
  holistically across all stages
- If all stages are back-pressured, upscale the most downstream stage first
  to unclog the pipeline

### GPU-Accelerated Preprocessing (Stripe + Nvidia)
- If a CPU stage is pegged at 100% for minutes → candidate for GPU
- cuDF is now a first-class batch format in Ray Data
- GPU shuffle via Rapids NVF: 4x faster, 2-3x cheaper than CPU shuffle
- Fuse consecutive GPU operations to avoid CPU↔GPU round-trips
- Hash shuffle reduction: move thresholding earlier in categorical encoding
  to reduce payload pulled to driver

### Driver-Side Bottlenecks
- Categorical encoding with long-tail categories: partition-level stats are
  huge; add intermediate map-reduce step before driver merge
- PyIceberg copy-on-write upserts are single-threaded on driver — caused
  OOM at 8GB heap (HeartFlow); pivot to Athena for distributed upsert
- Normalize schemas before processing — mismatched Arrow struct fields
  cause assertion errors at scale (Zoox)

---

## Storage Integration Patterns

| Format | Best For | Integration Notes |
|---|---|---|
| **Parquet** | Universal interchange, training input | `ray.data.read_parquet()` with predicate pushdown; tune file size to reduce S3 LIST overhead |
| **Lance** | Multimodal datasets, incremental column backfill | Zero-cost column addition; fragment-level progress tracking; billions of rows indexed in <14 min |
| **Iceberg** | Enterprise lakehouse, ACID upserts | Built-in Ray Data writer (fixed in recent versions); Unity Catalog integration in Ray Data |
| **LeRobot** | Robotics episode data | `ray.data.read_lerobot()` groups episodes by shared video files for 15-135x fewer file opens |
| **Delta Lake** | Versioned feature stores, time-travel queries | Polars + Delta Table for predicate pushdown; compaction jobs for read performance |
| **S3/Object Store** | Raw blob storage | CoreWeave CAIOS: NVMe caching layer delivers 7GB/s per GPU; cache is global across nodes |

### Key Storage Lessons
- **Keep storage close to compute**: CoreWeave's integrated NVMe cache
  sustained 120GB/s reads across 46 CPU nodes
- **Avoid writing from map stages**: Any IO in map/flat_map blocks Ray's
  interleaving of read→transform→write (Zoox)
- **Coalesce on write**: Use `min_rows_per_file` to prevent tiny file
  proliferation that kills downstream S3 listing performance
- **LanceDB for multimodal search**: Exa indexes billions of documents with
  Ray actors handling heterogeneous CPU/GPU stages, Lance providing
  fragment-level job resumability and zero-copy reads

---

## Architecture Decision Records

### When Ray Data Beats Manual Ray Core
CoreWeave A/B tested directly: Ray Data achieved 75% of Ray Core's GPU-time
for the same captioning workload — meaning Ray Data was more efficient,
finishing faster. The streaming execution, automatic back-pressure, and fault
recovery eliminated hundreds of lines of manual orchestration code.

### When to Consider Spark Instead
Uber's experience: Spark still has an edge for pure statistics aggregation
(mean, stddev, quantiles) at extreme scale. Ray Data excels at the transform
path — Uber achieved 19x less CPU time with 3x less memory for their
700M-row feature transform pipeline vs Spark baseline. Consider hybrid:
Spark for stats fitting, Ray Data for transforms.

### Actor-Only Future (v2.60+)
Ray Data is deprecating mixed task/actor model. Benefits: per-actor buffer
limits prevent spilling, better pipeline parallelism from submitting
multiple tasks to long-lived actors, simplified debugging. Minimal API
changes; existing APIs remain backwards compatible.
