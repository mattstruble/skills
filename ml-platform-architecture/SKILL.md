---
name: "ml-platform-architecture"
summary: "ML platform architecture: maturity models, cluster topology, GPU admission control, migration frameworks, and platform engineering patterns for production ML"
type: "design"
description: "You MUST consult this skill when designing or evolving an ML platform, choosing between self-managed and managed Ray/Kubernetes, architecting multi-tenant GPU clusters, implementing GPU admission control (Kueue, quotas, preemption), planning migration from one serving infrastructure to another, designing workload isolation (namespaces, IAM, env separation), building golden paths for ML engineers, or deciding cluster topology (single heterogeneous vs multi-cluster). Also trigger when evaluating build-vs-buy for ML infrastructure, designing cost attribution for GPU workloads, or architecting hybrid cloud/on-prem compute routing. NOT for model architecture, training algorithms, or inference engine internals — only the platform layer."
---

# ML Platform Architecture

**The hardest problem in ML infrastructure is not running one model — it is making the 50th team productive without the platform team becoming a bottleneck.**

Every platform decision trades developer velocity against operational complexity. Get the abstraction layer wrong and you either block teams or drown in custom infrastructure.

---

## Platform Maturity Model

Platforms evolve through predictable stages. Skipping stages creates debt; over-building early wastes effort.

| Stage | Characteristics | Trigger to advance |
|---|---|---|
| **1. Ad-hoc scripts** | Individuals run training on whatever compute they find; no orchestration | Second team needs GPUs |
| **2. Shared cluster** | One Ray/K8s cluster, homogeneous workers, shared capacity | Noisy-neighbor incidents; GPU starvation across teams |
| **3. Multi-tenant isolated** | Namespace isolation, per-team quotas, dedicated clusters per domain | Teams blocked waiting for platform team to provision |
| **4. Self-service platform** | Golden paths, CLI/SDK submission, GitOps deploys, cost attribution | Cross-region or hybrid-cloud requirements |
| **5. Unified ecosystem** | Single control plane across clouds/on-prem, automated workload placement | — |

**Real-world progression timelines:**
- Recursion: ad-hoc scripts → prefect + K8s jobs → Ray + Anyscale (~1 year migration)
- Discord: organic Ray adoption → self-managed KubeRay → Anyscale managed (platform 2.0)
- Coinbase: SageMaker → self-managed Ray on EKS → Anyscale managed (~18 months total)
- Capital One: fragmented siloed tools → unified KubeRay ecosystem
- Adyen: notebooks + Argo workflows → Ray on-prem (streaming data + multi-node training)

**Key insight:** Every company that started with a shared single cluster hit noisy-neighbor problems within a year. The question is not whether to isolate — it is when.

---

## Cluster Architecture Patterns

### Single Heterogeneous Cluster

One Ray cluster with multiple worker groups, each mapped to different hardware profiles.

**When to use:** Single team with multi-phase jobs (data prep → train → eval), workloads with distinct CPU and GPU phases.

**Pattern (Robinhood):** Define worker groups with taints/labels (e.g., `gpu-small`, `gpu-large`, `cpu-only`). Karpenter node pools select right-sized instances per group. Ray's resource-aware scheduling pins tasks to appropriate workers.

**Results:** 67% cost reduction, ~4× runtime improvement on large training workloads by separating CPU preprocessing from GPU training.

**Pattern (Spotify Hendrix):** Heterogeneous clusters with sidecar containers per worker group. Each runtime (training, inference, feature store) gets its own specialized image. Communication between Ray host actor and sidecar via network protocol buffers. Trade-off: runtime independence for communication overhead.

**Pattern (Grab):** Same training code, different topology YAML files. Tested 8×A100 single-node, 2×4-GPU multi-node, 8×single-GPU — only config changes, zero code changes.

### Multi-Cluster (Dedicated Per Domain)

Separate Ray clusters per team or model domain, managed by a control plane.

**When to use:** Multiple teams with different SLAs, blast radius concerns, or distinct dependency requirements.

**Pattern (Coinbase):** Migrated from one shared cluster to ~20 dedicated Anyscale clusters with 10 different instance types, scaling up to 500 nodes per cluster. Eliminated noisy-neighbor issues. Cost attribution per team became trivial.

**Pattern (Spotify Hendrix):** Multiple GKE clusters across regions. Teams spin up Ray clusters in their namespace. Kueue handles admission control across the fleet.

**Pattern (BMW):** One Ray service hosting multiple models via worker groups (vLLM workers, vLLM Omni workers). Routing via LiteLLM proxy to either self-hosted or hyperscaler APIs.

### Hybrid Cloud / On-Prem

**Pattern (Recursion CAKE):** Priority-aware routing layer on top of Anyscale. Jobs submitted with uniform parameters; CAKE routes to on-prem BioHive (zero marginal cost, data locality) or cloud (burst capacity). Low-priority jobs wait for on-prem; high-priority burst to cloud.

**Pattern (Adyen):** Fully on-prem with own GPUs and data warehouse. Ray enabled streaming from HDFS → serialize → transform → train → log in one pipeline, replacing materialization-heavy notebook workflows.

---

## GPU Admission Control

GPUs are the scarcest resource. Without admission control, teams either hoard or starve.

### Kueue Pattern

| Component | Purpose |
|---|---|
| **LocalQueue** | Namespace-scoped; maps to a team |
| **ClusterQueue** | Fleet-wide; maps to GPU reservations or shared headroom |
| **Cohort** | Groups ClusterQueues for borrowing across teams |
| **ResourceFlavor** | Maps to GPU types (A100, H100, T4) |

**Spotify implementation:** Workloads submitted as Ray jobs → Kueue evaluates → DWS provisions capacity → job admitted → resources reclaimed on completion. Production workloads get priority over experimental. Teams can pull from shared fleet headroom when their reservations are insufficient.

**Discord implementation:** Kueue integrated with Anyscale operator. Production, dev, and staging share the same GPU pool with priority queues. Production always runs; dev/staging backfill.

**Capital One implementation:** Per-trial resource isolation in hyperparameter search. Hard per-GPU memory limits via KubeRay prevent one bad configuration from crashing adjacent workers.

### Preemption and Priority

- Define priority classes: `production` > `staging` > `experiment`
- Use Kueue's preemption policies to evict lower-priority workloads when capacity is needed
- Robinhood: spot instances for validation workers; scale to zero when not in use

### Cost Control Patterns

- **Working-hours-only hosting:** BMW serves coding models 14hrs/day Mon-Fri, reducing GPU costs ~60% vs 24/7
- **Break-even analysis:** BMW calculated self-hosted open-source models break even at 8-16 developers (depending on model class) vs frontier API costs
- **Per-job cost attribution:** Recursion pairs Anyscale jobs with experiment metadata, surfaces GPU utilization and costs into BigQuery tables for per-plate cost queries

---

## Migration Decision Framework

### When to Migrate: Self-Managed → Managed Service

| Signal | What it means |
|---|---|
| Platform team > 50% time on operations | You're building an infra company, not shipping ML |
| Cluster provisioning takes days/weeks | Teams are blocked; velocity lost |
| Networking across VPCs is a bottleneck | Control plane needs to sit outside your clusters |
| No canary deploys or safe rollbacks | Risk of production incidents on every deploy |
| GPU scheduling is manual or FIFO | Wasting money on idle GPUs |

**Coinbase migration approach:**
1. Already had offline workloads on Anyscale → added online serving to consolidate
2. Used serving gateway to shadow production traffic to Anyscale
3. Validated parity on latency, throughput, model scores
4. Swapped primary traffic to Anyscale; kept legacy warm for rollback
5. Eventually deprecated legacy clusters
6. Result: deployment from days → minutes; one YAML + one command

**Discord migration approach:**
1. Swapped KubeRay open-source operator for Anyscale operator
2. Zero code changes for end users — "one small diff, reviewed in minutes"
3. First model: 40% faster with zero code changes (better GPU distribution)
4. Added Kueue for priority queuing alongside Anyscale operator

### When to Stay Self-Managed

- Regulatory requirements mandate full infrastructure control
- On-prem-only deployment (Adyen: fully on-prem, own GPUs)
- Team has deep Kubernetes expertise and capacity to operate
- Workloads are stable and well-understood (no rapid scaling needs)

### Build vs Buy Heuristic

> If operating the platform requires ≥ 2 additional engineers, the managed service likely costs less than the salaries + benefits. — Recursion's calculus

---

## Platform Engineering Patterns

### Golden Paths

A golden path is the supported, paved route to production. Make it so easy that no one wants to go off it.

**Lila Sciences model:**
- **Green path (on-platform):** Straight shot — platform handles security, GPU quotas, observability, reproducibility
- **Purple path (custom):** Still reaches compute, but requires more securitous route through security boundary
- **Red path (off-platform):** Hits security boundary and gets blocked

**Implementation patterns:**
- CLI wrapper (Lila's Chariot): one-stop shop for auth, job launch, status checks, log routing
- Hydra configs (Lila): researcher edits only what they care about — training hyperparams, compute config, run type — in one unified YAML. Chariot + Flyte Hydra Launcher translates config to infrastructure
- Configuration-as-code (Coinbase): team-owned YAML files, version controlled, deploy with single command via GitHub Actions

### GitOps for ML Infrastructure

**Pattern (Lila Sciences):** Argo CD + Crossplane for declarative infrastructure. Users deploy Ray Serve models via PR to a segregated repo. Platform auto-creates ingress, RBAC, and supporting resources around the Ray service.

**Pattern (Coinbase):** Dedicated model code repos per team. PR opens → auto-deploy to dev cloud. Merge → deploy to prod. Anyscale provides canary + auto-rollback.

### Developer Experience Investments

| Investment | Impact | Example |
|---|---|---|
| **Internal CLI** | Eliminates auth chain breakage, surfaces job status | Lila's Chariot, Discord's X-ray |
| **Training recipes** | Battle-tested defaults for attention, FSDP, masking | Spotify Hendrix recipes |
| **Template-based generation** | Reduces hallucination in AI-assisted config generation | Anyscale Agent Skills |
| **Composable workflows** | Swap training cores without changing infra | Spotify's routing layer over Ray Torch Trainer |
| **Unified config** | One source of truth for compute, hyperparams, run type | Lila's Hydra unification |

---

## Workload Isolation

### Namespace Isolation

Standard Kubernetes namespace per team. Each team gets:
- Own KubeRay clusters within their namespace
- RBAC via Kubernetes role-based access control
- LocalQueue in Kueue mapped to their namespace
- Resource quotas and limits

**Autodesk Ray Lab:** Researcher requests a project (not hardware). Workspace provisioned via JupyterHub. Each project mapped to a K8s namespace with RBAC.

### Cluster-Level Isolation

For stronger isolation, dedicate entire clusters per domain:
- **Coinbase:** ~20 clusters, one per model domain. Eliminates blast radius. Teams own their cluster configs.
- **Lila Sciences:** Ephemeral Ray clusters per team. Kueue + Kyverno for policy enforcement per organization.

### Environment Separation

- **Anyscale clouds (Recursion):** Control plane on Anyscale infrastructure; workloads run in customer VPC. Data never leaves corporate network.
- **Coinbase:** Same Anyscale separation — control plane manages infra, but data/artifacts/dependencies stay in Coinbase VPC.

### Data Privacy Patterns

- **BMW AI Gateway:** Self-hosted models for data-sensitive use cases (data stays in corporate network). Route to hyperscaler APIs only when data privacy is not a concern.
- **Adyen:** Fully on-prem. Payments data never leaves their network. Ray runs on their own GPU clusters with HDFS storage.

---

## Observability Stack

A platform without observability is a platform without trust.

| Layer | Tools | What to monitor |
|---|---|---|
| **Cluster health** | Grafana, Prometheus, Ray Dashboard | GPU utilization, node health, autoscaler behavior |
| **Job progress** | Ray Dashboard, custom UIs | Task completion, stragglers, data pipeline throughput |
| **Cost** | BigQuery/custom tables, Anyscale console | Per-job GPU-hours, per-team spend, idle GPU time |
| **Application** | LangFuse, MLflow, W&B | Model metrics, experiment tracking, eval results |
| **Logs** | Grafana Loki, Humo, CloudWatch | Centralized logs with alerts for failures |
| **AI-specific** | OpenTelemetry, LangFuse | Token usage, latency per model, request traces |

**BMW stack:** OpenTelemetry collector → Grafana (system metrics) + LangFuse (AI observability). Metrics collected from every component including vLLM engine-level stats.

**Robinhood pattern:** DCGM metrics → Grafana dashboards. Track GPU utilization, SM activity, SM occupancy, VRAM usage. Ray Dashboard for per-node GPU view. This observability muscle was prerequisite to identifying the heterogeneous cluster optimization.
