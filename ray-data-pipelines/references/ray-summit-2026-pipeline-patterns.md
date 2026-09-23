# Ray Summit 2026 — Pipeline Patterns Reference

Detailed patterns, concrete numbers, and implementation specifics extracted
from 13 Ray Data pipeline talks at Ray Summit 2026.

---

## 1. LeRobot Dataset v3.0 — Robotics Dataset Streaming
**Source**: Anyscale — [n0C1igDgNAU](https://www.youtube.com/watch?v=n0C1igDgNAU)

### Problem
LeRobot v3 stores video files spanning multiple episodes and episodes spanning
multiple video files. Naive parallel reads open each video file ~45x on average
for the XVLA-softfold dataset (1,500 episodes).

### Solution: Episode-Grouped Reads
- `ray.data.read_lerobot()` groups episode reads by shared video files
- XVLA-softfold: 99 read tasks with 300 file opens vs 1,500 tasks with 4,600 opens (15x fewer)
- Droid dataset (100K episodes): 135x fewer video file opens
- All planning happens on driver before streaming begins — safe at petabyte scale

### Key Implementation Details
- Per-dataset statistics travel with each row (constant per dataset)
- Combining multiple datasets: must have aligned column keys; mismatches caught at plan time
- Delta timestamps (window access): decoded frames cached within episodes, reused across consecutive rows
- Episode selector provides predicate pushdown — filters at read time, not downstream
- Integration with Ray Train: `iter_torch_batches()` for automatic sharding and back-pressure
- API is alpha as of Ray Summit 2026

### Architecture
```
Driver (plan) → Read Tasks [grouped by video files] → Decode MP4 frames
→ Stream PyArrow blocks → Preprocessing → Ray Train (auto-shard)
```

---

## 2. OOMs to 2x Throughput — C++ Isolation at Zoox
**Source**: Zoox — [ckfP6i9JWPc](https://www.youtube.com/watch?v=ckfP6i9JWPc)

### Problem
Robotaxi sensor data in proprietary C++ format. C++ extractors via pybind11
cause: memory leaks (invisible to Python GC), hangs (Python signals can't
interrupt), seg faults (kill the actor). Previous sequential pipeline
materialized everything on driver with `to_pandas()`.

### Solution: Four Isolation Techniques

**1. Disposable Process Isolation**
```python
@ray.remote(max_calls=1)
def extract_batch_isolated(batch):
    return cpp_extractor(batch)  # radioactive code

class ExtractorActor:
    def __init__(self):
        self.task_ref = extract_batch_isolated.remote(batch)
```
`max_calls=1` → each task gets fresh worker process → leaks confined.

**2. Completion-Order Collection**
```python
ray.wait(pending_list, num_returns=1, timeout=T)
```
Collect in completion order, not submission order. Critical for skewed data
where camera extraction: 2 min vs 6 min per record.

**3. Force-Kill on Timeout**
If no task completes within timeout → all pending tasks get `ray.kill()` via
process reference → move to next batch.

**4. Streaming Interleave**
```python
ds.repartition(N)
  .flat_map(fan_out_fn)
  .map_batches(extract_fn, compute=ActorPoolStrategy(...))
  .write_parquet(path, min_rows_per_file=K)
```
No IO in map stages. No intermediate writes. Let Ray interleave read→transform→write.

### Production Results
| Metric | Before | After |
|---|---|---|
| 300K records, 100 nodes | 14h, partial | 5h, complete, 2% error |
| 7M records, 200 nodes | 5d 19h | 2d 4h |

### War Stories
- **Block size**: Too large → first write after hours, can't validate early;
  too small → tiny S3 files. Use `min_rows_per_file` to coalesce.
- **Scheduling**: SPREAD strategy + skewed data = hot nodes. Default bin-pack
  scheduling understands per-node load. Equal task count ≠ equal load.
- **Schema normalization**: Mixed Arrow struct fields → assertion errors.
  Enforce uniform schema before processing.
- **Actor sizing**: 60 actors × 32GB > cluster capacity (1700GB). Tune based
  on the C++ remote task memory (8GB), not the orchestrating actor.

### Observability
- Ray Queue actor as failure sink: mapper drops failed record + reason, continues
- Failure reporter thread: periodic consolidation → `failure.parquet`
- Custom metrics reporter wrapping `ray.util.metrics` → Prometheus time series
- Latency heatmaps + task queue depth graphs for tuning actor count

---

## 3. 1600 GPUs Petabyte Pipeline — Video Captioning at CoreWeave
**Source**: CoreWeave + Anyscale — [N5T7l_TX2TI](https://www.youtube.com/watch?v=N5T7l_TX2TI)

### Scale
- 600TB video data, 70M captions, 1600 GPUs (RTX Pro 6000/B40), 95 minutes
- Brand new account → Ray running in 1 hour → production in 24 hours

### Pipeline
```
CAIOS (S3) → CPU nodes (FFmpeg decode, key frame extraction)
           → GPU nodes (VLLM captioning) → CAIOS (write captions)
```

### Bottleneck Resolution Sequence
1. **Repartition**: Ray Data saw 150 blocks for 70M videos → repartition to
   match available parallelism. GPU utilization: 10% → 25%
2. **Explicit GPU allocation**: Tell Ray Data exactly how many GPUs to use.
   Utilization: 25% → 54%
3. **CPU:GPU ratio tuning**: Infer CPU count from GPU inference speed.
   Utilization: 54% → ~100%

### Key Insight
"Starvation looks like satisfaction" — throughput appears fine when GPUs
aren't saturated because Ray Data doesn't auto-infer optimal hardware counts.

### Fault Tolerance
- 1500 of 1600 GPUs active; 100 held as replacements
- Failed inference engines auto-replaced; failed nodes kicked out
- Zero stalls, zero boot failures across entire 600TB run
- Linear throughput scaling: 256 GPUs ≈ same per-GPU throughput as 1500 GPUs

### Storage: CoreWeave CAIOS
- S3-compatible object storage with NVMe caching (LOTA) on compute nodes
- 8× 7.68TB NVMe drives per node; global cache shared across all nodes
- Sustained 110-120 GB/s reads to 46 CPU nodes (~2.4 GB/s per node)
- VLLM model loading on 256 nodes: 17GB in 2 seconds (LOTA cache)
- No egress fees, no per-request fees, no inter-region fees

---

## 4. Petabyte Video Curation — Ray Data vs Ray Core
**Source**: CoreWeave — [NnsuPkqyWGw](https://www.youtube.com/watch?v=NnsuPkqyWGw)

### Direct Comparison
- Same workload, same hardware: Ray Data used only 75% of Ray Core's GPU time
- Ray Data handles streaming, orchestration, back-pressure, multi-stage
  parallelism automatically
- Key differentiator: Ray Data ensures GPUs are never starved by managing
  CPU→GPU data flow

### Design Principles
1. **Stream in stages**: Pipeline parallelism via Ray Data
2. **Scale resource pools independently**: CPU and GPU node counts vary independently
3. **Keep storage close to compute**: CAIOS integrated caching

### Post-Pipeline Storage
- Customers use Iceberg, Parquet, or increasingly LanceDB for captioned output
- Ray object store (in-memory) for immediate downstream if data fits
- CAIOS for persistent petabyte-scale storage

---

## 5. Ray Data on GPU — Preprocessing at Stripe
**Source**: Stripe + Nvidia — [4vHpltz8KRU](https://www.youtube.com/watch?v=4vHpltz8KRU)

### Problem
Economy-size datasets: 6-10TB, ~2B rows tabular data. Pre-processing
(standard scaling, categorical encoding) is the bottleneck before training.
Data is time-bound (fraud detection) — can't precompute once.

### GPU Preprocessing Results
| Metric | CPU Ray | GPU Ray | Improvement |
|---|---|---|---|
| Fit time | baseline | 5x faster | 82% cheaper |
| vs Spark (production) | 15x faster | 32x faster | 96% cheaper |

### Key Techniques

**MapReduce Stats with Large Categories**
- Long-tail categorical encoding: partition stats are huge
- Solution 1: Add intermediate map-reduce step to shrink partition count
  before driver merge
- Solution 2: Hash shuffle reduction — move columns of same type to same
  partition, apply thresholding early before global aggregate

**Chain Optimization**
- Stateful preprocessors (need fit) create natural pipeline breaks
- Group stateless transforms together; fuse previous transform with next fit
- Result: 50x speedup from fewer dataset scans

**GPU-Specific PRs (Nvidia → Ray Data)**
1. cuDF as native batch format — eliminates manual CPU↔GPU transfers
2. GPU shuffle via Rapids NVF — hash partition on GPU, UCX/NVLink transport
3. Grouped aggregations on GPU — count, min, max, mean natively
4. GPU-accelerated preprocessors (ongoing)

**GPU Shuffle Results**: 4x faster, 2-3x cheaper per run vs CPU shuffle
(tested A100 through H100)

### Best Practices
- Target GPU acceleration at stages where CPU is pegged at 100%
- GPUs want large batch sizes — different from CPU
- Minimize CPU↔GPU transfers; fuse consecutive GPU operations
- Driver-side merge is the scalability ceiling for map-reduce patterns

---

## 6. Ray Data What's New — Architecture Redesign
**Source**: Anyscale — [Qyji-PNYZQ0](https://www.youtube.com/watch?v=Qyji-PNYZQ0)

### Problem: Spilling in Heterogeneous Clusters
Old design: stage-level back-pressure via global resource manager that treats
entire cluster as one big node. GPU nodes with smaller object stores overflow
→ spill to disk → cascading GPU idle time.

### Solution: Per-Actor Buffer Limits (v2.60+)
- Ray Data becomes actor-only (deprecating mixed task/actor model)
- Each actor gets proportional subdivision of its node's object store
- Actors on smaller nodes get smaller buffers → chunk data more aggressively
- Guarantee: if all actor buffers sum ≤ object store, no spilling

### New Actor Pool Sizing
Old: greedy per-operator decision based on input buffer alone
→ upscales infer actors when input is full, but output is already full → immediate back-pressure

New: holistic view of all operators' input AND output buffers
→ upscale most downstream stage first to unclog the pipeline

### Results
- Memory imbalance shrank dramatically
- Zero spilling in tested workloads
- 10% runtime improvement (from no spilling + better actor pipelining)

### Disk-Based Shuffle
Old: quadratic object references on head node; reactive spilling; actor death loses hash partitions

New: Each mapper writes one file to node-local disk. Object store holds only
small handles (path + byte offsets). Reducers access data via AeroFlight
file server on each node. Benefits: linear scaling, controlled memory, fault-tolerant.

### New Data Sources
- LeRobot, LanceDB (robotics/multimodal)
- Unity Catalog, Iceberg (enterprise)
- DataSource v2 API: more flexible, memory-aware reading by default

### Fusion as a Choice
Fusing read + GPU inference → GPU used only 33% of time.
Unfusing → 3x higher GPU utilization. Ray Data gives primitives for both.

---

## 7. Exa Web Indexing — Billion-Document LanceDB Pipeline
**Source**: Exa — [fbbNmhWBS3Q](https://www.youtube.com/watch?v=fbbNmhWBS3Q)

### Architecture: XAD Framework (Three Layers)
1. **Logical layer**: DAG of column definitions with strong typing; type errors
   caught before execution (fail fast when jobs cost $10K+)
2. **Storage layer (Lance)**: 2D layout (rows × columns grow independently);
   zero-cost column evolution; fragment-level completion tracking
3. **Execution layer (Ray)**: Heterogeneous actors for CPU/GPU stages;
   actors live only while work exists; auto scale-down

### Lance Storage Key Properties
- Fragments (row groups) × data files (column groups) = 2D growth
- Add new column = add new data file to existing fragment; no rewrite
- Fragment-level progress = job metadata; diff real vs planned state to find remaining work
- Global unique row IDs for constant-time access
- S3-native: file-based manifests, S3 primitives for transactions
- Benchmarks: billions of rows indexed in <14 minutes on <10 nodes; 30K QPS from single instance

### Ray Usage
- Ray actors represent compute stages (tokenize on CPU, embed on GPU)
- Topological sort of DAG → execution plan → compiled to Ray actors
- Heterogeneous actors with different resource profiles in one Python script
- Pipelined execution: CPU tokenization and GPU embedding overlap
- Zero-copy message passing via shared memory for co-located actors

### Design Principle
Fuse same-resource operations (e.g., two CPU ops). Split across resource
boundaries (CPU → GPU). Same heuristic as Motive's asymmetry framework.

---

## 8. GammaLake Feature Storage — Point72
**Source**: Point72/Cubist — [1MR9ln9iGp0](https://www.youtube.com/watch?v=1MR9ln9iGp0)

### Problem
Hedge fund with many independent trading teams. Each team has different data
shapes (dense/sparse/event-driven features), different scales, different
access control requirements. Existing options (KDB, QuestDB, ClickHouse) each
had gaps for time-series feature storage.

### Solution: GammaLake
- Modular feature groups stored as separate Arrow tables with shared sortable index
- Reads: scan + horizontal Arrow concatenation (cheap metadata operation)
- Missing features represented as nulls (implicit from Arrow layout)
- Writes incur cost to maintain index alignment; reads are fast
- Backed by Delta Lake (versioning, time-travel, compaction) or Lance or Parquet

### Ray Usage
- Local Ray as parallel processing engine for the complex dependency graph
  of append/read operations
- Leverages Ray's efficient Arrow serialization for inter-process data movement
- Robert Ishihara's insight: Ray works well as "purposedriven multiprocessing"
  even for local workloads

### Performance
- Feature group addition: O(1) cost (just append) vs O(n) for full Parquet rewrite
- Read latency: competitive with DuckDB benchmarks
- Open-sourced on Point72 GitHub

---

## 9. Heterogeneous Pipelines — Motive
**Source**: Motive — [7veFC1SeV5o](https://www.youtube.com/watch?v=7veFC1SeV5o)

### Problem
Driver safety ML pipeline: multiple models (eye closure, yawn, lane drift)
→ fusion → scoring. Testing new model versions requires replaying entire
graph. 10K+ videos per test run.

### Key Finding: Fused > Modular (Sometimes)

**Approach A (Modular)**: 5 separate Ray Data stages, each with own worker pool
**Approach B (Fused)**: Fetch+decode+infer in one GPU actor; fuse+score in CPU actor

Result: **B was faster** despite less elegant code.

**Why**: Decoded frames are ~100MB per video. Passing through Ray Data
serializes → copies to object store → deserializes. This overhead + object
store pressure + scheduling overhead per stage outweighed the parallelism gains.

### Three Asymmetry Heuristics (Most Important Takeaway)
1. **Cost asymmetry** (GPU vs CPU) → supports splitting
2. **Change-frequency asymmetry** (models change less often than fusion params) → supports caching the expensive stage
3. **Payload asymmetry** (>10MB between stages) → supports fusing to avoid serialization

### Caching for Combinatorial Testing
- Cache GPU inference results keyed by (dataset_id, video_id, model_id, model_version)
- 4.8x median speedup; most testing is parameter tuning on fusion/scoring
- 6 model combinations → only 7 unique model runs needed (not 6 full graphs)

### Scaling
- Linear with GPU count: 4 GPU → 4x speedup, 16 GPU → ~16x speedup
- Fractional GPUs: `num_gpus=0.25` to pack 4 replicas per GPU for small models
- Previous custom implementation → refactored to Ray Data: what took 6 months of testing now takes hours

---

## 10. Koba/KoJo — Disaggregated Data Loading at Luma AI
**Source**: Luma AI — [jAf3ZkJR0_I](https://www.youtube.com/watch?v=jAf3ZkJR0_I)

### Koba: Unified Multimodal Data Loader
- PyTorch-native, composable pipeline: sampling → Lance read → processing → packing
- Supports text, image, audio, video, robotics actions — same API
- Deterministic randomness (seed → deterministic data stream, required for scaling laws)
- Fast metadata resume: training resumes from exact cursor position after failure
- Runtime filtering with alerting on unusual filter rates

### KoJo: Disaggregated Compute Pool
Offloads heavy compute from training hosts to separate Ray-managed pool.

**Architecture**:
```
Training Node (Koba control plane) → sends corpus references
→ KoJo Pool [fetch → decode → VAE encode] → returns compact latents
→ Training Node continues with small tensors
```

**Two Pipeline Modes**:
1. Decode-only offload: cheap CPU/GPU pool, but high network transfer
2. Fused decode + VAE encode: powerful GPUs needed, but 12x smaller response per clip

### Key Designs
1. **Stripe routing**: Proxyless client-side routing; bounded failover with immediate shedding on overload
2. **Distributed caching**: Results keyed by (corpus_id, stage, seed, processor_version);
   9x fewer GPU-hours with caching; only caches deterministic correct results
3. **Three-layer overload control**: Per-worker cap (ms), cross-pool mixing (seconds), KubeRay pod recovery (minutes)

### Production Results
| Metric | Smaller Model | Larger Model |
|---|---|---|
| Step time reduction | 17% | 9% |
| 99th percentile tail latency | Significant reduction | Significant reduction |
| Peak HBM savings | Up to 58% | Up to 58% |
| Avg resident memory savings | 44% | 44% |

Post-training recipe (16 trainers + 2 KoJo workers): 42% step-time reduction.
1:8 KoJo:trainer ratio sufficient. Fault recovery: 1 step to absorb killed replicas,
2.5 min to restore throughput.

**Cost overhead**: 2.9% (small model) to 1.7% (large model) of GPU-hours.
Audio-only model: 55% GPU cost savings via amortized tokenization.

### Infrastructure
- KubeRay manages Ray cluster lifecycle
- 1 GPU per KoJo worker; pod affinity to avoid fragmentation
- Largest pool: 11K-core KubeRay cluster
- Hundreds to thousands of Ray clusters launched daily across training/serving

---

## 11. PyTorch Training on Uber Michelangelo
**Source**: Uber — [lhOq0h7KPK8](https://www.youtube.com/watch?v=lhOq0h7KPK8)

### Native Transform: Spark → Ray Data Migration

**Production Workload**: Uber Eats home feed generative recommendation
- 4.5B rows, 100TB+ Parquet input, 26 weeks of data, 100 workers
- Transform pipeline: read Parquet → aggregate stats → map_batches with PyTorch module → write Parquet

**Performance**: 19x less CPU time, 3x less memory vs Spark baseline.

**Optimization Path** (cumulative 15x throughput gain):
1. Baseline Ray default config: 23 hours
2. Custom scheduling loop (batched metadata fetch, incremental usage update): 1.7x
3. Increased file size / reduced file count (lower S3 metadata overhead): additional gain
4. Increased block size (less scheduling overhead): additional gain
5. PyArrow batch format + fused transform tasks: final gain

### Reliability Issues Encountered
| Issue | Fix |
|---|---|
| Head node OOM | Upgrade Ray version; avoid scheduling tasks on head node |
| Read/write failures | Reduce file count; set `retry_transient_errors` |
| Chunked array incompatibility | Fallback to Polars reader (open Ray OSS ticket) |
| Schema unification failure | Cast all label columns to fixed float type |
| Object spill limit | Bump object store memory + spill volume; cap reads per worker |
| Cluster allocation failure | Start workers after head is initialized |

### Data Loading: Petastorm → Ray Data Migration

**Shadow Validation Framework**:
- Run Petastorm and Ray Data simultaneously on production pipelines
- Three signals: model performance (hard gate), training time (hard gate), GPU utilization (soft signal)
- AI agents automate: pipeline update → shadow run → comparison → migration recommendation

**Shuffle Configuration**:
- Platform default: file-level + buffer-level shuffle (comparable to Petastorm row/row-group)
- Block and global shuffle: opt-in only (high object store cost)
- Reproducibility bug: shuffle repeated identically every epoch. Fix: set seed = base_seed + epoch

**Key Optimization**: Dedicated producer thread for batch preparation
- CPU batch prep (Arrow→NumPy + collation) was 50-70% of per-batch time
- Moved to background thread: while GPU trains batch N, producer prepares batch N+1
- Pipeline 2: from 28% slower than Petastorm → 55% faster
- Pipeline 5: from 22% slower → 26% faster

**GPU Utilization vs SM Active**: Some pipelines showed lower GPU utilization but
nearly doubled SM active (actual compute). Training time + SM active are stronger
signals than utilization alone for data-bound workloads.

---

## 12. Synthetic Data Flywheel — Pinterest
**Source**: Pinterest — [wmNLd05bqGs](https://www.youtube.com/watch?v=wmNLd05bqGs)

### Problem
Post-training data for Pinterest Assistant (navigator VLM) doesn't exist at
scale. Synthetic generation pipeline: seed → generator model (GPU) → tool calls
(network IO) → scorer model (GPU) → output formatting (CPU). Sequential
execution: 334 hours for 10K rows.

### Solution: Ray Data Streaming Pipeline
```
Input seeds → Rollout (GPU/VLLM) → Tool Calls (Ray actors, concurrent network)
→ Scoring (GPU/VLLM) → Output formatting (CPU)
```

**Key Optimizations**:
1. **Repartition once upfront**: 256 partitions at read time, maintained through
   entire pipeline. No inter-stage repartition → no gaps → GPUs stay saturated.
2. **Dynamic GPU reallocation**: First-stage GPUs finish faster (seeds → subqueries).
   After 2-3 min idle, reallocated to scoring stage → all 8 GPUs blast through
   the larger scoring workload.

### Results
| Version | Time (10K rows) | Speedup |
|---|---|---|
| Single machine sequential | 334 hours | 1x |
| Ray Data v0 (static pools, no partitioning fix) | 2h 41min | 124x |
| Ray Data v1 (dynamic reallocation + upfront repartition) | ~1.5h | 227x |

All on same 8-GPU hardware. No horizontal scaling — purely pipeline optimization.

### Operator Framework
- Reusable operator library: rollout, tool_call, scoring
- Different teams compose operators via Python job config
- Navigator (shopping assistant): VLLM rollout → API tool calls → VLLM scoring
- Canvas (image editing): PyTorch diffusion → no tool calls → VLLM scoring
- Same pipeline, different operator composition

### Forward-Looking: Iterative DPO
Split input → training set (synthetic generation → SFT/DPO data) + evaluation set
→ fine-tune model → score on held-out evaluation → iterate.

---

## 13. Medical Image Pipelines — HeartFlow
**Source**: HeartFlow — [f4BLia48tEU](https://www.youtube.com/watch?v=f4BLia48tEU)

### Problem
Petabyte-scale multimodal medical data lake (3D heart scans, segmentations,
blob data in S3 + structured metadata in relational DBs). Need analytics
pipeline from raw blobs to insights.

### Architecture: PAL (Production Analytics Pipeline)
**Orchestration**: Dagster (asset model: bronze/silver/gold as three assets with
declared dependencies; materialization records for lineage)

**Compute**: Two separate Anyscale clouds
- Ingest cloud (bronze): IO-bound work — URL fan-out to nodes, lazy loading, stream own data
- Analytics cloud (silver + gold): compute-bound — distributed PyArrow transforms and aggregations

### Medallion Architecture on Ray Data
| Layer | Operation | Ray Data Usage |
|---|---|---|
| **Bronze** | Copy S3 blobs → Parquet | Ray Data distributes URL fan-out; workers stream own data; batch size and repartition auto-tuned |
| **Silver** | Parse raw JSON bytes → structured columns | Vectorized PyArrow row transforms via `map_batches` |
| **Gold** | Group-by aggregation → case-level metrics | Ray Data aggregation across distributed batches |

### Publishing: PyIceberg → Athena
**Failed approach**: PyIceberg copy-on-write upserts single-threaded on driver.
All Ray Data blocks funneled into one commit. Some tables needed 8GB driver heap
→ OOM. Ray Data and commit competed for same driver heap. Scaling cluster didn't
help — commit is serial on one process.

**Working approach**: Athena reads staging Parquet from S3, performs distributed
upsert. Driver holds no data, just issues SQL commands.

### Dagster ↔ Anyscale Integration
- No native Dagster-Anyscale integration; built custom using Dagster Pipes
- Channel: S3 (both can reach it; messages are metadata/status)
- Flow: Dagster writes run context to S3 → Anyscale job reads context → writes status to inbound prefix → Dagster watches in real-time
- Messages are S3 objects; 7-day lifecycle expiry

### Developer Experience
- PAL SDK: plain English specs → AI generates decorator class → codegen produces
  Dagster assets + Anyscale job + load test CI
- RoboPAL: AI agent analyzes failed Anyscale jobs, sends root cause to Slack,
  opens fix PRs. Uses Anyscale memory bank (Hindsight) for cross-failure learning.

### Key Numbers
- Autoscaling via Anyscale for both daily runs and multi-year backfills
- Spot instance scheduling for cost optimization
- Cluster limits to prevent accidental expensive bills
