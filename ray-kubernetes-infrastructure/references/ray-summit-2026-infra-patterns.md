# Ray Summit 2026 — Infrastructure Patterns Reference

Detailed patterns, concrete numbers, and implementation specifics extracted
from 13 Ray-on-Kubernetes infrastructure talks at Ray Summit 2026.

---

## 1. Data Center Shapes Workload — NVLink/InfiniBand Topology
**Source**: NScale — [7lyBqNsFVcQ](https://www.youtube.com/watch?v=7lyBqNsFVcQ)

### Key Concepts
- **Front-end network** (Ethernet): SSH, code upload, storage (NVMe, model weights, training data, KV cache offload). Congestion risk if workloads are front-end heavy.
- **Back-end network**: Optimized for peer-to-peer RDMA between GPUs. Either RoCE (multi-planar topology for giant scale) or InfiniBand + NVLink.
- **InfiniBand hierarchy**: Developed by Mellanox (acquired by NVIDIA ~8 years ago). Within a scale unit = one hop over nearest switch = slightly faster bandwidth. Across scale units = extra hop over spine. Ask providers if capacity is within same scale unit.
- **NVLink evolution**: Fastest peer-to-peer GPU bandwidth. Previously constrained tensor/expert parallelism to single node. GB200/GB300 NVL72 = 18 compute trays per rack. Roadmap: NVL576 (8 racks) — larger than a scale unit.
- **Impact on workloads**: Models will keep getting bigger. RL weight transfer benefits enormously — faster NVLink enables more on-policy training or larger models at same off-policy level.

### NVLink Sharp
- Switches now do compute: AllReduce aggregation happens at ASIC on NVSwitch/InfiniBand switch, not GPU round-trips.
- Benchmark (1 rack): 920 GB/s with NVLink Sharp vs 338 GB/s without = **2.7× speedup**.

### CPU-GPU Collocation Decision
- Collocate when: latency is critical (CPUs in hot path of AI workload), or strong networking/security story (minimize north-south traffic, keep data east-west within DC).
- Separate when: no latency sensitivity (e.g., ahead-of-time pre-tokenization).
- Use cases requiring standalone CPU nodes: agentic RL loops, VM sandboxes.

### NScale Control Center
- Validates everything during DC bring-up: GPUs (multi-day stress tests surfacing XID/remapping errors), CPU nodes, backend/frontend fabric (port flapping, cable checks), storage.
- End-to-end production workload validation earns NVIDIA Exemplar status.
- Discovers non-obvious optimal defaults: NCCL env vars, PCIe configurations, topology-aware Linux services. Baked into cloud images.
- State-of-the-art hardware (GB300, Vera Rubin) often doesn't ship with optimal defaults.

---

## 2. Notion Multi-Region — Environment Isolation with Terraform
**Source**: Notion — [bmACTn-hAMs](https://www.youtube.com/watch?v=bmACTn-hAMs)

### Problem
Notion expanded from US-only to US/EU/JP/KR. Initial approach: copy-paste US Anyscale cloud to each region. Result:
- No dev/prod boundary within regions; same project, same IAM roles
- Same control plane role and cluster role across all clouds — no real region isolation
- Mix of Terraform and manual operations; inconsistent patterns across regions
- AI coding agents confused by inconsistent infrastructure patterns

### Solution: Separate Cloud Per Environment Per Region
8 Anyscale clouds (US/EU/JP/KR × dev/prod). Each with scoped IAM role pair.

**Two-phase Terraform registration**:
1. Create scoped IAM roles + AWS resources + register cloud → Terraform outputs cloud ID
2. Put cloud ID back into config + terraform apply → locks permissions to specific cloud ID
3. Window between phases should be as short as possible

### Migration Steps
1. Inventory all Anyscale jobs/services (environment, region, S3/KMS/secrets/Kafka requirements) — used Codex + Claude
2. Consolidate legacy US-west and EU stacks into shared layout with APAC regions
3. Create scoped IAM role pairs; split S3/KMS policies by region + environment
4. Clean up secrets: move to AWS Secrets Manager in same region as reading cloud, prefix with dev/prod
5. Update all Ray jobs/services to read from new secret names
6. Register new clouds via Anyscale Terraform provider (beta); gate per workspace

### Terraform Provider Import Challenges
- Import path was least-tested code path in beta provider
- False replacement in terraform plan = provider bug, not config error
- Reported issues directly to Anyscale team; fixes usually within hours
- Iterative: adopt, test, report, fix, re-adopt

### Key Lessons
1. Multi-region without permission isolation is theater — US-west-2 could still write to EU
2. Real isolation boundary = IAM + networking + data access, not logical labels/tags
3. Adopting new tools is two-way: import path only battle-tested because Notion exercised it

---

## 3. One Cluster End-to-End — SageMaker HyperPod + Kueue
**Source**: AWS — [MFyBXjacCXQ](https://www.youtube.com/watch?v=MFyBXjacCXQ)

### Four Building Blocks
1. **Queuing**: Kueue in front of Ray for efficient multi-team resource sharing
2. **Managed developer environments**: VS Code/Jupyter collocated with GPU cluster; out-of-box observability (Prometheus + Grafana pre-configured)
3. **Multi-tenant interface**: Namespace-based isolation per team on SageMaker Studio
4. **Resilient infrastructure**: Auto-recovery of failed instances; tiered checkpointing

### Kueue Specifics for Ray
- **Priority**: Inference serving production traffic > weekend experiments
- **Fair-share with borrowing**: Each team gets floor capacity; idle capacity lent to other teams; reclaimed when needed
- **Gang admission**: Training jobs get all-or-nothing pod scheduling (partial admission = stalled job holding GPUs)
- **Elastic admission** (feature flag): Scale up Ray cluster without losing head pod state; avoids suspend/resume that destroys in-memory cluster state
- **Visibility**: Queuing position exposed so data scientists know when job will run

### Checkpointing Strategy
- Problem: Infrequent checkpointing = hours of lost work on failure; frequent checkpointing = throughput loss
- Solution: **Tiered checkpointing** — frequent in-memory/in-cluster checkpoints + periodic sync to durable object store
- Infrastructure auto-recovery: Listen to GPU signals → reboot or replace failed nodes → jobs run uninterrupted

### Inference Resilience
- External KV cache store enables warm replicas from first request during scale-up events

---

## 4. Platform Orchestration — Anyscale on Azure/K8s
**Source**: Anyscale — [37FEm2XTa98](https://www.youtube.com/watch?v=37FEm2XTa98)

### Industry Trends
- >50% of Ray community runs on Kubernetes
- Kubernetes provides: single security/ops model, bin packing to reduce fragmentation, scaling with demand, ecosystem (KubeRay, Kueue/Kai, Kubeflow/Argo)
- Portability: ML pipelines move between clouds without rewriting infrastructure

### Anyscale KubeRay Connect (Private Preview)
- **Problem**: Anyscale operator creates/manages pods directly; doesn't understand KubeRay CRDs. Adoption required rewriting job specs, GitOps repos, tooling.
- **Solution**: Mutating webhook patches existing KubeRay specs at admission, injecting lightweight data plane sidecars. KubeRay operator continues reconciling CRs.
- **Architecture**: Connector (control ops, syncs state, mutating webhook) + Cluster Telemetry Gateway (OTel collector + sidecars) + Observability API (deployment serving telemetry)
- **Design decisions**: Control split from telemetry for fault tolerance (connector only needed at pod lifecycle start; if Anyscale crashes, workloads continue), security (split identity), scalability (independent auto-scaling)
- **Three tiers shipping in order**: Observe → Orchestrate → Proprietary workload optimizations (Q4/Q1)

### Anyscale Scheduler
- Unified priority-aware queuing + cross-region capacity search
- Kubernetes-native: generates Kueue manifests into data plane
- Multi-cloud/multi-cluster: same compute config across any registered region/cluster
- Retired machine pools (historically fragile); single config for K8s and VMs

---

## 5. Evolving Ray Core — GCS Fault Tolerance + Isolation
**Source**: Google — [07XyCSjIwqQ](https://www.youtube.com/watch?v=07XyCSjIwqQ)

### Scalability Improvements
- **Resource sync optimization**: Previously, new resource changes continuously created broadcasts while previous sync in-flight. Now: accumulate updates during in-flight broadcast, merge, send together in next broadcast. Reduces N² synchronization pressure.
- **Task throughput**: 1.6× higher in core benchmarks → 23% faster batch inference, 24% faster Shovel execution
- **Placement group creation**: 300× faster at 10K nodes (45 min → 9 seconds; 18 nodes per PG)
- **Actor scheduling**: 40K actors on 10K-node cluster. Exploring centralized authoritative view for actor scheduling to bypass distributed resource sync.
- **Task event offloading** (2.58): Offload high-volume events from GCS to reduce control plane pressure

### GCS Fault Tolerance
- **Embedded RocksDB**: Local disk operations; lifecycle tied to Ray head; no external Redis dependency. LinkedIn contribution, integrated with KubeRay.
- **Active-passive GCS** (ongoing): K8s lease-based leader election. Passive acquires leadership on failure, recovers state, takes over behind same K8s head service endpoint. Workers see no endpoint change.

### Cgroup Resource Isolation
- Separates Ray system processes from application workloads
- Benchmarks: zero OOM kills, zero node failures from contention, predictable completion times
- Critical for data processing where resource usage varies significantly across tasks/stages

### Ray Direct Transport (RDT)
- Handles accelerator-specific communication libraries (NCCL, NIXL, TPU Sync)
- RL weight transfer benchmarks: Qwen3-235B in 3.5 seconds (SkyRL), GLM-4.5-Air (355B) in 2.3 seconds (Miles)
- Approaching beta; expanding beyond GPUs to TPUs and other accelerators

### Native Sandbox Integration (Experimental)
- GVisor-based: user-space kernel intercepts all Linux syscalls; strong isolation without touching host kernel
- Sub-millisecond startup latency; low memory footprint per container; low idle CPU
- Hundreds/thousands of sandboxes per Ray node for agentic RL trajectories
- Roadmap: checkpoint/suspend/resume sandboxes, scalability improvements, pluggable backends

---

## 6. Full-Stack Observability — K8s Events in Ray Dashboard
**Source**: Google — [-TpQ3s95O1o](https://www.youtube.com/watch?v=-TpQ3s95O1o)

### The Observability Gap
When Ray runs on K8s, infrastructure failures are opaque to ML practitioners:
- Application masking: kernel panic, GPU PCIe drop, OOM → surfaces as generic Python error or silent worker disconnect
- Siloed tools: Ray dashboard tracks tasks/actors; K8s events live in API server or external logging
- Context switching: ML engineers forced to kubectl, dmesg, or file access tickets to cluster admins
- High MTTR: expensive GPUs sit idle during ticket/investigation cycles

### Platform Events Architecture (Ray 2.58, merged upstream)
**Three layers**:
1. **Ingestion**: K8s events provider in Ray head dashboard process. Watches Ray CRs + associated pod events using in-cluster service account. Client-side label filtering (only pods belonging to active Ray cluster).
2. **Schema**: Provider-agnostic Protobuf (extensible to Slurm, other cloud events). Events stored in bounded configurable LRU ring buffer. Zero footprint on Ray head performance.
3. **UI**: Dedicated Platform Events tab. Filter by severity (info/warning), platform (K8s), object kind (pod, RayCluster, RayJob, RayService). Shows image pull latency, failed scheduling reasons, OOMKilled events.

### Event Export Pipeline
- Events converted to Ray canonical event format (same schema/timestamps/severity as task/actor/driver events)
- Streamed to structured JSON line files alongside existing telemetry
- Configurable log rotation + async write buffers (zero impact on Ray execution)
- Parse with Fluentbit/Vector/Promtail → export to Grafana/CloudWatch/Datadog/Kafka
- Unified alerting: correlate K8s spot preemptions with training metrics in corporate Grafana

### Selective Node Event Forwarder (KubeRay roadmap)
- **Problem**: Node-level events (GPU ECC faults, XID errors) emitted on K8s node objects, not pod objects. Ray user pods can't watch cluster-wide node events (RBAC security concern).
- **Solution**: New controller in KubeRay operator running with cluster-wide RBAC. Watches node events → applies configurable regex/allowlist → maps to active Ray pods on that node → re-emits as correlated warning on parent RayCluster CR.
- UI result: "Infrastructure failure detected on node X: XID 31 error on GPU UID Y" — directly in Ray dashboard, no cluster admin escalation needed.

### Feature Gate
`RAY_DASHBOARD_ENABLE_PLATFORM_EVENTS=true` in Ray head pod manifest.

---

## 7. GB200/GB300 Scheduling — Topology-Aware Placement Groups
**Source**: NVIDIA — [4AmKOKbieus](https://www.youtube.com/watch?v=4AmKOKbieus)

### Why Existing Placement Groups Failed for Rack-Scale Hardware
- `STRICT_PACK`: Tries to put all bundles on same node. 16 GPUs requested but each node has 4 → fails.
- `STRICT_SPREAD`: No locality guarantee across nodes → bundles scattered across racks.
- Result: Users lost NVLink bandwidth, increased fault surface, spent late nights debugging.

### Topology Strategy API
```python
pg = placement_group(
    bundles=[{"GPU": 4}] * 16,
    strategy="STRICT_PACK",
    topology_strategy={"strategy": "STRICT_PACK", "topology": "rack"}
)
```
- Few extra lines of code on top of existing placement group API
- Ray guarantees all bundles on same rack/NVLink domain
- Multi-rack: chain in Python for loop; configure spares per rack

### Fault Tolerance Scenarios
1. **One node fails, spare in rack**: Auto-reschedule to spare node (invisible to user)
2. **One node fails, no spare in rack**: Bundle left pending; visible via state API. Reschedules when node returns.
3. **Entire rack fails**: Migrate all bundles to spare rack if available
4. **Minimum guarantee**: Can specify minimum nodes per rack; job doesn't schedule if minimum not met but uses extras if available

### NVIDIA Groot N1.7 Benchmark
- Scale: 512 GB300 GPUs (128 nodes), 100K training iterations
- Run 1 (scheduler assigns any nodes, scattered across racks): baseline
- Run 2 (mandated 8 racks, topology-aware): **14.4% throughput improvement**
- GB200 estimate: 20–30% improvement (half the east-west bandwidth of GB300)
- Cost projection (10K GPUs, $13.31/GPU-hr): **$16.7K saved per training hour**

### Future Directions
- Account for data center → AZ → rack hierarchy and Vera Rubin topology
- Inference-oriented strategies (e.g., strict spread across racks)
- KubeRay integration to remove manual topology identifiers from ray start command
- Integration with Kai/Volcano for K8s-level topology-aware pod scheduling

---

## 8. Anyscale on Azure — BYOC Deployment
**Source**: Microsoft — [rJ1yBqWFOU0](https://www.youtube.com/watch?v=rJ1yBqWFOU0)

### Architecture
- **Control plane**: Anyscale-managed (dev tools, observability, APIs, orchestration)
- **Data plane**: Customer's AKS subscription + VNet. Model weights, training data, KV caches, inference traffic never leave Azure boundary.
- **Security**: Private Link, NSGs, Azure CNI policies. Entra ID end-to-end. Workload Identity for pod credentials. Azure IAM for RBAC. No long-lived keys.

### Deployment Flow
1. Azure Portal → search "Anyscale Services" → Create
2. Pick subscription, resource group, region, cluster name, AKS cluster
3. Configure storage account for logs/metrics (stays in customer subscription)
4. Create Entra ID identity → deploy

### Enterprise Governance
- ARM-native provisioning; resources inherit Azure Policy
- Discoverable via Azure Portal like any other Azure service
- Private cluster Terraform template available for regulated industries
- Currently public preview; GA imminent

### Production Customers
- **Wayve** (UK autonomous driving): Petabytes of multimodal video/audio data processing + model training
- **Zūprl** (Spanish satellite imagery): Millions of km of data, trained within seconds

---

## 9. Ray History Server — Post-Mortem Ephemeral Clusters
**Source**: KubeRay — [UWjMK_mtH0s](https://www.youtube.com/watch?v=UWjMK_mtH0s)

### The Problem
Ephemeral clusters (RayJob auto-teardown) destroy in-memory dashboard on termination. Options:
- Keep cluster alive for dashboard → exhausts expensive GPU/TPU quotas on idle compute
- Tear down immediately → lose all observability

### History Server Architecture
**Two components**:

1. **Collector** (sidecar per pod):
   - Reads Ray logs from shared tmpdir volume
   - Receives Ray events (task, actor, job, node, worker) via HTTP from local aggregation agent
   - Disk-first pipeline: immediate append to local JSON lines → rotate at time/size threshold → async upload to object storage
   - Handles: graceful shutdown (final scan + upload), session transitions (detect old session, archive), crash recovery (logs preserved on shared volume after restart)
   - Back-pressure: stops accepting event batches when local disk hits threshold
   - Config: shared between head/worker collectors except `ray_role` field

2. **Server** (stateless K8s deployment):
   - On-demand loading: sessions loaded only when user opens them
   - Bounded LRU cache: recently viewed snapshots cached; evict least-recently-used at memory limit
   - Replays events from object storage → serves standard Ray Dashboard APIs
   - Horizontally scalable; each instance does own lazy loading + in-memory caching
   - UI: lists all terminated clusters; click to enter familiar Ray Dashboard experience

### Supported Backends
GCS (Google Cloud Storage), S3, Azure Blob

### Collaboration
Google + Anyscale + Alibaba. 100+ PRs. Beta in KubeRay 1.7.

### Roadmap to GA
- Observability metrics for history server itself
- Simpler configuration through RayCluster API
- Dashboard lifecycle management

---

## 10. Scaling Ray on K8s — KubeRay Roadmap
**Source**: KubeRay — [srmgiZdIpXk](https://www.youtube.com/watch?v=srmgiZdIpXk)

### Adoption Examples
- **xAI**: Multimodal image/video training data preparation on Ray + K8s
- **NVIDIA**: Groot robotics foundation model; 1,024 GPU training via Osmo (K8s workflow orchestration) + Ray for distributed training/data ingestion
- **Microsoft**: MAI Syncing + MAI-1 (near 1 trillion parameters). Ray across pre-training, RL, inference, evaluation, CPU data pipelines
- **Platform adoptions**: Uber, Spotify, Apple, ByteDance, Reddit, Pinterest, Shopify

### KubeRay 1.6–1.7 Feature Summary
**Ephemeral clusters**: History Server beta, RayCronJob
**Cluster management**: K8s RBAC auth (Ray 2.55 + KubeRay 1.6), mTLS + network policies (Red Hat), Ingress API (Microsoft)
**Runtime interoperability**: In-place pod resizing (alpha), K8s Workload API for gang scheduling (Microsoft), embedded RocksDB for GCS (LinkedIn)

### Roadmap
1. **K8s Workload API continuation**: Composite PodGroups (K8s 1.37); topology constraints on pod scheduling
2. **Admission webhook for node label forwarding**: K8s node labels → pods → Ray processes → topology strategy API for placement groups
3. **End-to-end observability**: Node event forwarder in KubeRay → Ray Dashboard

---

## 11. LLM on TPUs — SlicePlacementGroup + First-Class TPU Support
**Source**: Google — [yMcejOWY1I4](https://www.youtube.com/watch?v=yMcejOWY1I4)

### TPU Architecture Primer
- Custom accelerators for dense matrix multiply; chips within slice connected via ICI (optical 2D/3D torus mesh)
- Slice = indivisible hardware unit; missing/misordered chip → collective communication deadlock
- XLA compiler expects synchronized env vars across all TPU VMs in slice
- Standard schedulers treat accelerators as fungible → cross-slice scheduling → indefinite XLA hang

### Ray TPU Integration (Ray 2.55+, GKE collaboration)
Four layers:
1. **Ray Core**: Native topology-aware scheduling; SlicePlacementGroup API
2. **Docker images**: Pre-packaged `-tpu` suffix images with libTPU, PGRT drivers, tpu-info
3. **Testing**: Release pipeline integration tests + GKE end-to-end tests on real TPU hardware
4. **Library support**: Ray Train, Ray Serve, Ray Data all support TPUs

### SlicePlacementGroup API
```python
spg = SlicePlacementGroup(topology="2x2x4", version="v4")
ray.get(spg.ready())
results = dispatch(spg, my_spmd_task)
```
- **Multi-slice**: `num_slices=N` → reserves N independent physical slices; returns unified placement group
- **Separate PGs**: `pg_per_slice=True` → list of placement groups for different workloads
- **Dynamic sub-slicing**: `SubSlicePlacementGroup(subtopology="2x2x2", version="v4")` → carves geometrically valid partition from pre-provisioned large slice; eliminates capacity stranding

### Ray Serve LLM on TPUs
- Declarative config: specify `accelerator_type: TPU`, `topology: "2x2x4"` in LLMConfig
- Under the hood: vLLM TPU engine with custom Pallas/XLA fused attention kernels
- PagedAttention in TPU HBM reduces KV cache fragmentation
- Features: autoscaling (dynamic TPU slice provisioning), prefix-aware routing, direct streaming
- Production deployment via RayService YAML: zero-downtime rolling upgrades (KubeRay 1.7)

### Ray Train on TPUs
- JAX: host-centric (1 worker per TPU VM); PyTorch: device-centric (1 worker per chip)
- Unified ScalingConfig: just change accelerator type + topology
- Multi-slice training: increase num_workers proportionally
- Elastic training: min/max worker range; job continues on available slices; all slices must have same topology
- JIT preemption checkpointing: `ray.train.get_preemption_info()` returns deadline + affected ranks; GKE gives ~30s warning; failure domain is entire slice (one host preempted → whole slice goes)
- Ray Data integration: `iter_jax_batches()` for automatic sharding + prefetching; data ingest dashboard for bottleneck detection

### TPU Observability
- Per-node tensor core utilization charts in dashboard
- TPU metrics table integrated into Ray dashboard
- XProf trace triggering via native TensorBoard plugin integration

### GKE Integration Details
- Ray operator add-on: managed KubeRay + admission webhooks in K8s control plane
- Node auto-provisioning: dynamic TPU node pool scaling
- DRET (Dynamic Resource Allocation Networking): high-throughput secondary NICs for pod-to-pod TPU communication
- Mutating webhook intercepts pod creation → injects JAX/PyTorch env vars, worker IDs, hostnames, pod affinity/anti-affinity rules
- Informative labels on Ray nodes: slice name, host index, topology

---

## 12. Ray Train Observability — NCCL Hang Detection + JIT Checkpoint
**Source**: Anyscale — [svFhsSdCgqg](https://www.youtube.com/watch?v=svFhsSdCgqg)

### Three Common Distributed Training Failures

#### 1. Data Starvation
- GPUs idle waiting for slow data loading → unstable utilization → jittering between loading and training
- Root cause often buried in specific transformation stage (e.g., slow CPU collate operation)
- **Solution**: Ray Data's data loader splits loading into 6 standardized stages with per-stage timing
- Live dashboard: average batch cycle breakdown, per-stage latency, per-rank stragglers, pipeline delivery vs ingest throughput
- Grafana panels for lifetime metrics; open-source with custom Prometheus

#### 2. NCCL Hangs
- NCCL requires all ranks call same collectives with same shapes/dtypes/order; one rank failing to send → infinite wait
- PyTorch timeout: ~30 minutes; by then all training progress lost
- **NVIDIA RAS** (Reliability, Availability, Serviceability, added NCCL 2.24): separate thread per GPU counts collectives; queryable to detect mismatches
- **Ray Train Active Hang Detector** (coming soon):
  - Background thread polls RAS periodically (zero performance impact)
  - Detects count stagnation (~10 minutes) before PyTorch error
  - Time window allows running diagnostics before job kill
  - Auto-saves to experiment directory: RAS collective counts, per-rank stack traces, PyTorch Flight Recorder, per-node nvidia-smi
  - All diagnostics captured on first failure — no rerun needed
  - Integrates with Anyscale hardware diagnostic panel

#### 3. Node Preemption
- Spot/scheduler reclaims nodes at any time → lose training progress since last checkpoint
- Checkpointing more frequently doesn't solve root problem (still loses progress between checkpoints)
- **`ray.train.get_preemption_info()`**: Returns PreemptionInfo with deadline, affected nodes/ranks
- Training loop checks for preemption signal → save JIT checkpoint → reload from JIT checkpoint on restart

### JIT Checkpointing Cost Analysis (Qwen3-8B, 4× H100 spot)
- 2,000 training steps, periodic checkpoint every 500
- 2 preemptions during run → 672 recomputed steps → 1+ hour wasted GPU time
- Periodic-only spot: 50% cheaper than on-demand
- JIT checkpointing: recomputed steps drops to 4 (100× less waste); **60% cheaper than on-demand** (extra 10% savings over periodic-only)

---

## 13. GPU Observability — Physical Topology Visualization
**Source**: Datadog — [bDG8f5KGetw](https://www.youtube.com/watch?v=bDG8f5KGetw)

### The Observability Unit Problem
- Device-level metrics necessary but insufficient; healthy GPU ≠ healthy training job
- Synchronous distributed training advances at pace of slowest rank
- Delayed rank gates synchronous process group → propagates across thousands of otherwise healthy GPUs
- Finding straggler ≠ finding cause (could be application, runtime, network, node, or hardware layer)

### Meta Llama 3 Reference Numbers
- 16K+ GPUs, multi-month pre-training
- ~1 failure every 3 hours; >50% GPU-related
- >90% effective training time maintained
- Fleet cost: ~$36M/month; 1% efficiency loss = **$4.3M/year**

### Datadog GPU Monitoring Architecture

#### Training Run View
- Preserves Ray job + training run identity; connects each worker's world rank to process, host, GPU, traces, physical topology
- Identifies slow steps + straggler ranks + deviation from peers
- No more manually inspecting hundreds of graphs per worker

#### AI-Powered Root Cause Analysis (MCP + Bits AI)
- Assembles causal narrative: triggering fault → mechanism → cascade across peers → recommended actions
- Example: hardware fault on one node → ECC/XID signals → NVLink recovery → step time spike → MFU drop
- Distinguishes affected synchronization peers from largely unaffected nodes

#### Continuous Tracing (<2% overhead)
- Correlates CPU execution → GPU execution
- Shows sequence of work within step; identifies long synchronization calls
- Example: CUDA synchronization call consuming 166ms (>80% of trace)
- Connects spans back to Python call sites (optimizer step → collective ops → training loop lines)

#### Physical Topology Visualization
- Groups affected workers by shared physical infrastructure (host, rack, GPU, link)
- Pattern recognition: errors concentrating in single rack → investigate shared rack-level dependency
- Changes diagnosis from "multiple independent GPU failures" to "shared infrastructure issue"

### Investigation That Motivated the Product
- Customer reported unexplained MFU drop on large pre-training run
- Agent restarts and memory errors were plausible but turned out to be red herrings
- Actual cause: NVLink fabric issues; XID events + physical layer retransmissions were leading indicators
- Without connected context: months to resolve. With: days.
