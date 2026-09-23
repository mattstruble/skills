---
name: "ray-kubernetes-infrastructure"
summary: "Production patterns for running Ray on Kubernetes with topology-aware scheduling, fault tolerance, and full-stack observability"
type: "engineering"
description: "Consult this skill when deploying Ray clusters on Kubernetes via KubeRay, designing topology-aware placement for NVLink/TPU/InfiniBand hardware, configuring GCS high availability, building multi-region or multi-cloud Ray platforms, debugging training failures with the Ray History Server or platform events, or evaluating GPU observability stacks. Trigger on questions about rack-aware scheduling for GB200/GB300, TPU slice placement groups, NCCL hang detection, preemption handling, or KubeRay operator lifecycle. NOT for Ray Data pipeline design patterns (see ray-data-pipelines), Ray Serve routing logic, or general Kubernetes administration."
---

# Ray on Kubernetes Infrastructure

**The scheduling topology — not the cluster size — determines training throughput.**

Production Ray-on-K8s deployments fail most often from three causes:
topology-unaware placement fragmenting interconnects, opaque infrastructure
failures hiding behind generic Python errors, and missing post-mortem
observability for ephemeral clusters. The patterns below address all three,
drawn from 13 infrastructure talks at Ray Summit 2026.

---

## KubeRay Operator Architecture

KubeRay is the open-source Kubernetes operator for Ray, written in Go.
It provides CRDs (RayCluster, RayJob, RayService, RayCronJob) to
declaratively manage Ray clusters on Kubernetes.

### Lifecycle

| Year | Milestone |
|------|-----------|
| 2022–23 | ByteDance donates initial operator; generative AI drives adoption |
| 2024 | Hardening: CRD maturity, scalability, 1.0 GA release |
| 2025 | Open-source standard; deeper K8s primitive bridging |
| 2026 | Co-engineering era: K8s workload API integration, topology strategies |

### Key CRDs
- **RayCluster**: Head + worker group pods; autoscaler-managed
- **RayJob**: Ephemeral cluster per job; auto-teardown on completion
- **RayService**: Long-lived serving with zero-downtime rolling upgrades (beta in 1.7)
- **RayCronJob** (1.7): Scheduled repetitive Ray jobs

### KubeRay 1.6–1.7 Features
- **History Server** (beta): Post-mortem dashboard for terminated clusters
- **K8s RBAC authentication**: Native token auth via TokenReview + SubjectAccessReview APIs; works with OIDC/Entra ID
- **mTLS + network policies**: Red Hat contribution for security compliance
- **Embedded RocksDB**: LinkedIn contribution; GCS persistence without external Redis
- **In-place pod resizing** (alpha): Autoscaler resizes running pods before adding new ones
- **K8s Workload API**: Microsoft contribution; native gang scheduling via PodGroup objects without third-party schedulers
- **Ingress API integration**: Microsoft contribution; customizable ingress behavior
- **Node label forwarding webhook** (roadmap): Propagate K8s node labels → pods → Ray processes for topology strategy API
- **Selective node event forwarder** (roadmap): Forward filtered node-level hardware events to Ray dashboard

### Platform Integrations
- **GKE**: Managed Ray operator add-on, node auto-provisioning, DRET networking for TPUs
- **AKS/Anyscale on Azure**: ARM-native provisioning, Entra ID, workload identity, private networking
- **SageMaker HyperPod**: Kueue integration, managed dev environments, tiered checkpointing
- **Anyscale KubeRay Connect** (preview): Mutating webhook injects observability sidecars onto existing KubeRay CRDs; keeps KubeRay operator as reconciler

---

## Topology-Aware Scheduling

### The Core Problem
Standard schedulers treat accelerators as fungible. Requesting 64 GPUs may
scatter them across 16 racks, losing 2.7× NVLink bandwidth and increasing
fault exposure. For TPUs, cross-slice scheduling causes indefinite XLA hangs.

### Hardware Topology Hierarchy

```
Data Center
 └─ Availability Zone
     └─ Scale Unit (InfiniBand)
         └─ Rack / NVLink Domain (GB200: 72 GPUs, GB300: 72 GPUs)
             └─ Compute Tray / Host (4 GPUs + 2 ARM CPUs + 4 ConnectX NICs)
                 └─ GPU
```

### Network Fabrics

| Fabric | Scope | Bandwidth (GB200) | Notes |
|--------|-------|--------------------|-------|
| NVLink (intra-rack) | Within NVLink domain | High bandwidth (TB/s class) | NVSwitch on back of rack |
| InfiniBand / RoCE (inter-rack) | Across racks | 400 GB/s (GB200), 800 GB/s (GB300) | Hierarchical; within-scale-unit faster than cross |
| Front-end Ethernet | Storage, SSH, management | Varies | Congestion risk if workloads are front-end heavy |
| TPU ICI | Within TPU slice | Dedicated optical | 2D/3D torus mesh; slice is indivisible |
| Data center network | Across TPU slices | Standard DCN | For multi-slice training |

### NVLink Sharp
Offloads AllReduce to dedicated ASICs on NVSwitch. Benchmark: 920 GB/s vs
338 GB/s without (2.7× speedup on single rack). Ask providers if Sharp is
enabled.

### Decision Framework: When Topology Matters

| Workload | Topology Critical? | Why |
|----------|--------------------|-----|
| Tensor parallelism, expert parallelism | **Yes** — pack within NVLink domain | High per-step data movement |
| Pipeline parallelism, data parallelism | Less critical | Lower cross-boundary data volume |
| Pre-training AllReduce at scale | **Yes** — rack-aware placement | 14–30% throughput gain from bin-packing |
| RL weight transfer | **Yes** — NVLink domain | Enables on-policy training; faster weight sync |
| Batch inference / data processing | Usually no | Embarrassingly parallel; interconnect not bottleneck |
| TPU SPMD workloads | **Always** — slice atomicity | XLA deadlocks if chips span slices |

### Ray Topology Strategy API (Ray 2.55+)

#### GPU Rack-Aware Scheduling
```python
from ray.util.placement_group import placement_group

pg = placement_group(
    bundles=[{"GPU": 4}] * 16,       # 16 hosts × 4 GPUs = 64 GPUs
    strategy="STRICT_PACK",
    topology_strategy={
        "strategy": "STRICT_PACK",
        "topology": "rack"            # All bundles on same NVLink domain
    }
)
ray.get(pg.ready())
```

Fault tolerance is built-in:
- Node fails in rack → reschedule to spare node in same rack
- No spare in rack → bundle left pending; observable via state API
- Entire rack fails → migrate all bundles to spare rack if available

NVIDIA Groot N1.7 benchmark: 512 GB300 GPUs, 8-rack topology-aware vs
scattered → **14.4% throughput improvement** (estimated 20–30% on GB200 due
to lower inter-rack bandwidth).

#### TPU Slice Placement Groups (Ray 2.55+)
```python
from ray.util.accelerators.tpu import SlicePlacementGroup, dispatch

# Reserve one v4-32 slice atomically
spg = SlicePlacementGroup(topology="2x2x4", version="v4")
ray.get(spg.ready())

# Execute SPMD task across all hosts in slice
results = dispatch(spg, my_tpu_task)
```

- **Multi-slice**: `SlicePlacementGroup(topology=..., num_slices=4)` for pipeline parallelism
- **Dynamic sub-slicing**: Carve geometrically valid sub-slices from pre-provisioned large slices at runtime; eliminates capacity stranding
- **Elastic training**: `min_workers` / `max_workers` range; job continues on available slices

### Multi-Host Gang Scheduling on KubeRay
For TPU multi-host groups, set `numOfHosts` in worker group spec. GKE
mutating webhook injects pod affinity/anti-affinity rules + JAX/PyTorch
environment variables. Pods are atomically gang-scheduled to same node pool.

For K8s native gang scheduling without third-party schedulers, use
Kubernetes Workload API PodGroup objects (KubeRay 1.6 + K8s 1.36).

---

## Ray Core Reliability

### GCS High Availability

| Backend | Characteristics |
|---------|----------------|
| Redis (existing) | Network-based; separate lifecycle; Redis itself can be SPOF |
| Embedded RocksDB (new) | Local disk ops; lifecycle tied to Ray head; no external dependency |
| Active-passive GCS (in progress) | K8s lease-based leader election; passive acquires leadership on failure; workers use same K8s head service endpoint |

### Cgroup-Based Resource Isolation
Separates Ray system processes from application workloads using Linux cgroups.
Benchmarks show **zero OOM kills** from resource contention, zero node
failures, and predictable completion times.

### Scalability Improvements (Ray 2.55–2.58)
- **1.6× task throughput**: Fewer RPCs, less lock contention, faster lightweight op paths
- **300× faster placement group creation**: Merged resource sync broadcasts; 10K-node PG from 45 min → 9 seconds
- **40K actors on 10K nodes**: Combined PG + actor scheduling improvements
- **Task event offloading**: High-volume events offloaded from GCS to reduce control plane pressure

### Preemption Handling
```python
info = ray.train.get_preemption_info()
if info is not None:
    # info.deadline — timestamp when node will be reclaimed
    # info.affected_ranks — which workers will be lost
    save_checkpoint()  # JIT checkpoint before deadline
```

- GKE TPU: ~30 seconds warning
- AWS spot: ~120 seconds warning
- Qwen3-8B on 4× H100 spot: JIT checkpointing reduced recomputed steps from 672 → 4 (100× less waste), 60% cheaper than on-demand (vs 50% with periodic-only checkpointing)

### NCCL Hang Detection (Ray Train, coming soon)
- Background thread polls NVIDIA RAS (Reliability, Availability, Serviceability) collective counters
- Detects count mismatches before PyTorch 30-minute timeout
- Auto-saves diagnostics on first failure: RAS reports, per-rank stack traces, PyTorch Flight Recorder, nvidia-smi per node
- Zero performance overhead (runs on separate thread)

---

## Observability Stack

### Layer 1: Ray Dashboard + Platform Events (Ray 2.58+)
K8s events streamed into Ray Dashboard via lightweight background pull in
Ray head process. Feature gate: `RAY_DASHBOARD_ENABLE_PLATFORM_EVENTS=true`.

**What surfaces**:
- Pod lifecycle: image pull latency, OOMKilled, eviction, rescheduling
- Ray CR events: RayCluster, RayJob, RayService state transitions
- Node hardware faults (via selective event forwarder): XID errors, GPU ECC faults

**Architecture**:
- Provider-agnostic Protobuf schema (extensible to Slurm, other clouds)
- Client-side label filtering: only pods belonging to active Ray cluster
- Bounded LRU ring buffer: capped memory even in noisy clusters
- Events exported as structured JSON lines; compatible with Fluentbit/Vector/Promtail → Grafana/CloudWatch/Datadog

### Layer 2: History Server (KubeRay 1.7 beta)
Post-mortem replay engine for ephemeral clusters. Zero idle compute cost.

**Architecture**:
- **Collector** (sidecar): Uploads Ray logs from shared tmpdir + events via HTTP to object storage. Handles graceful shutdown, session transitions, and crash recovery.
- **Server** (stateless deployment): On-demand loading with bounded LRU cache. Horizontally scalable. Serves standard Ray Dashboard APIs.
- Supports GCS, S3, Azure Blob as backends.

**Collaboration**: Google + Anyscale + Alibaba; 100+ PRs.

### Layer 3: GPU Observability (Datadog / External)
Job-level diagnosis beyond device metrics:

- **Straggler detection**: Identify slow rank + deviation from peers per training step
- **Continuous tracing** (<2% overhead): Correlate CPU→GPU execution; link back to Python call sites
- **Topology visualization**: Group affected workers by shared physical infrastructure (host, rack, GPU link)
- **Root cause analysis**: Connect MFU/step-time changes to hardware faults (ECC, XID, NVLink recovery events)

Meta Llama 3 reference: ~1 failure every 3 hours on 16K GPUs; 1% efficiency loss = $4.3M/year on $36M/month fleet.

### Layer 4: Ray Train Data Ingest Observability
Live dashboard showing:
- Average batch cycle breakdown (exposed data loading time vs training)
- Per-stage latency: read → transform → collate → transfer → train
- Per-rank breakdown to identify stragglers
- Pipeline delivery throughput vs median worker ingest throughput
- Grafana panels for lifetime metrics; open-source with custom Prometheus backend

---

## Multi-Region / Multi-Cloud Deployment

### Notion Pattern: Environment-Isolated Anyscale Clouds
**Problem**: Single Anyscale cloud per region with shared IAM roles; dev/prod
co-mingled; no real data isolation despite multi-region labels.

**Solution**: Separate Anyscale cloud per environment per region (8 clouds for
US/EU/JP/KR × dev/prod). Each cloud gets scoped IAM role pair (control plane +
cluster). Two-phase Terraform registration locks permissions to cloud ID.

**Key lessons**:
1. Multi-region without permission isolation is not truly multi-region
2. Real isolation boundary is at IAM/networking/data access level, not logical labels
3. Terraform provider adoption is a two-way relationship — import path only tested because Notion exercised it

### Anyscale Scheduler (Multi-Cloud)
Unified interface for priority-aware queuing and cross-region capacity search.
Kubernetes-native manifest generation. Same compute config works across any
registered region/cluster/hyperscaler.

### SageMaker HyperPod Multi-Tenant Pattern
Namespace-based isolation per team. Kueue provides:
- Priority-based admission (production inference > weekend experiments)
- Fair-share with floor guarantees + idle capacity lending between teams
- Gang admission for training (all-or-nothing pod scheduling)
- Elastic admission (scale up without losing Ray head state)

---

## Hardware Topology Quick Reference

### NScale Validation Process
Before serving customers, stress-test every component: GPUs (multi-day
workloads surfacing XID/remapping errors), CPU nodes, backend/frontend
fabric (port flapping, cable verification), storage. Bake optimal configs
(NCCL env vars, PCIe settings, topology-aware Linux services) into images.
NVIDIA Exemplar status validates top performance across model families.

### GB200/GB300 Key Facts
- 18 compute trays × 4 GPUs = 72 GPUs per rack
- NVLink domain = full rack (NVL72); roadmap to NVL576 (8 racks)
- NVLink Sharp: AllReduce offloaded to switch ASICs
- Fault tolerance: node-level (spare in rack) vs rack-level (spare rack)
- Each compute tray: 4 Blackwell Ultra GPUs + 2 ARM Grace CPUs + ConnectX NICs

### TPU Key Facts
- Slices: indivisible hardware units; chips connected via ICI (optical 2D/3D torus)
- Scheduling: must land all workers on same contiguous physical mesh
- TPU v7: 2×2×2 slice = 8 chips across 2 hosts
- JAX: host-centric (1 process per VM); PyTorch: device-centric (1 process per chip)
- Sub-slicing: carve geometrically valid partitions from large slices at runtime
- GKE bootstraps XLA env vars via mutating admission webhook

### Switches Are Computers
InfiniBand and NVSwitch support in-network compute (Sharp). AllReduce
aggregation happens at the switch instead of node round-trips. Ask if Sharp is enabled.
