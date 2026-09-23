# Ray Summit 2026 — ML Platform Architecture Patterns

Cross-referenced evidence from 12 talks on ML platform design, cluster architecture, migration, and operations.

---

## Talk Summaries

### BMW AI Gateway (yKt-CpfrOIE)
**Speaker:** Thomas Riedel, AI Platform Engineer, Connected AI Platform
**Platform:** Central unified ML/AI platform for BMW. 35+ engineers across 6 teams, 4 countries. 550+ users, 60 use case teams, ~25M connected vehicles.
**Architecture:** LiteLLM proxy routes to Amazon Bedrock, Azure AI, or self-hosted Ray service. 120+ models across 7 modalities in 3 regions. One Ray service hosts all self-hosted models via worker groups (vLLM for autoregressive, vLLM Omni for diffusion/image/video). EFS caching layer for model weights. Karpenter for dynamic node scaling on AWS EKS.
**Key pattern — cost-driven self-hosting:** Replaced frontier API usage (Claude family) with self-hosted open-source models (GLM 5.2, MiniMax, Qwen 3.6) for agentic coding. Working-hours-only hosting (14hrs/day Mon-Fri). Break-even at 8-16 developers depending on model class. Pilot of 100 developers reported 50% cost savings on Opus-class workloads.
**Lesson:** Serving AI models vs routing to APIs is fundamentally different in operational complexity. GPU shortage in Europe is real. Performance tuning vLLM/Ray is per-model, not one-size-fits-all.

### Lila Sciences Platform (eHb9Z6AxdMk)
**Speakers:** Tyler Titworth (AI Platform Lead), Prich (MLOps Engineer). ~15 person platform team.
**Platform:** Self-service research platform for scientific super intelligence. Multi-cluster, multi-cloud, multi-region.
**Architecture:** Three verticals — workload execution (Flyte v1 + Ray), model serving (GitOps + Ray LLM Serve), sandboxing (Jupyter). Substrate: Kueue + KubeRay + Kyverno + OPA for policy enforcement. Ephemeral Ray clusters per team.
**Key patterns:**
- **Map task scaling:** Flyte's pod-per-task model caused 10K pod DDoS and scheduling fragmentation. Solved by fanning out inside Ray clusters instead of as separate pods.
- **Chariot CLI:** Internal CLI as single entry point — authenticate, launch jobs, check status, route to logs. Eliminated auth chain breakage across AWS/VPN/K8s/Flyte layers.
- **Hydra unification:** Unified training hyperparams, compute config, and run type into single Hydra config. Flyte Hydra Launcher translates config to infrastructure (Anyscale job, workspace, or E2E test harness).
- **GitOps:** Argo CD + Crossplane for declarative infra. Users deploy models via PR. Platform auto-creates ingress, RBAC, supporting resources.
- **Golden path:** Green (supported) → Purple (custom but reachable) → Red (off-platform, blocked at security boundary).
**Lesson:** Scientists don't need to learn Kubernetes. They need a CLI that makes the green path so easy nobody wants to do anything else.

### Agent Skills for Ray — Anyscale (DgRIx2AoyHQ)
**Speakers:** Kuning (Architect, LLM/Agentic AI), Aiden (DevX Engineer)
**Product:** Anyscale Agent Skills — coding agent skills (for Claude Code, Cursor, Codex, Copilot) that teach agents to deploy, debug, and optimize Ray/Anyscale workloads.
**Key patterns:**
- **Skills as decision aids, not knowledge dumps:** Agent asks only important questions, infers safe defaults for low-risk choices, explains trade-offs for consequential decisions.
- **Templates beat reference lists:** Validated templates reduce hallucination vs asking LLMs to generate configs from docs. Faster, more consistent.
- **Skills as software:** Version, validate against latest Ray/vLLM releases, deprecate when stale. Measure success rate on dedicated workload list.
- **Pre-commit hooks:** Block destructive commands before execution. Essential safety net.
- **Automatic skill handoff:** After workload skill generates code, platform skill auto-prompts "would you like to deploy?" Seamless chain.
**Lesson:** The future of ML platform UX may be natural-language-driven via coding agents, but the skills backing them need the rigor of software engineering.

### Recursion Virtual Biology Platform (7x1Ssp3MSto)
**Speakers:** Isa (ML Engineer, ML Infra, ~7 years), Alex (ML Engineer, ML Infra, ~3 years)
**Platform:** Processes ~60PB of biological/chemical/patient data (40PB proprietary). Phenomics (microscopy images), transcriptomics (gene expression), predictive chemistry, virtual cell.
**Architecture:** Prefect owns high-level workflow. Ray jobs submitted to Anyscale. Unit of work changed from K8s job (download all → inference) to Ray task (concurrent download + process, retry on failure). Hybrid: Anyscale on GCP + on-prem BioHive-2 (H100s, A100s).
**Key pattern — CAKE routing:** Compute Abstracted Kubernetes Engine. Priority-aware queue on top of Anyscale. Users submit with uniform parameters. Routing logic: maximize BioHive utilization (zero marginal cost) → burst high-priority to cloud → low-priority waits for on-prem. Same pipeline, same user experience regardless of placement.
**Key pattern — cost observability:** Anyscale jobs paired with experiment/project metadata. GPU utilization + cost surfaced into BigQuery for per-plate cost queries. Replaced guesswork with precise per-experiment cost tracking.
**Migration:** ~1 year from legacy K8s orchestrator + Prefect Cloud to Ray + Anyscale. Joint project with ML scientists — they now operate their own workloads; infra team manages platform.
**Build vs buy:** "If we were operating our own system, we'd need at least a couple more engineers. The salaries + benefits probably exceed the Anyscale cost."

### Discord ML Platform (rnanZRFbskk)
**Speakers:** Sarana (ML Platform), Alex (Applied ML, Quest team)
**Platform evolution:**
1. ML engineers already using Ray before platform team found it — organic adoption
2. Platform 1.0: Open-source KubeRay on GKE. Two paths — CLI for development (long-lived Ray clusters), Daxter for DAG orchestration. Used Dax-Ray for cross-VPC orchestration.
3. Platform 2.0: Anyscale operator replaced open-source KubeRay. Daxter kept for orchestration but Dax-Ray replaced by Anyscale executor. Kueue added for priority queuing.
**Migration result:** Zero code changes for end users ("one small diff, reviewed in minutes"). First model 40% faster just from operator swap. 90% compute reduction from one client who used new observability to identify waste.
**Quest ML model:** Started with XGBoost (scrappy/8020), hit MLOps scaling ceiling, rebuilt as shared multi-task neural ranker with multi-gate mixture of experts. Ray Data + Ray Train on 8 H100s. Processes 2B raw events → 30M training records in ~1 hour. Model 2× better after one year of iteration.
**Online serving pattern:** Keep heavy representation learning offline (batch embeddings into KV store). Serve only the lightweight MoE head on CPU via Triton (18ms median, 45ms P95). Cheap, fast, preserves latency budget for future complexity.
**Lesson:** Pick the right abstractions. Non-leaky abstractions meant the migration was invisible to model teams. Platform team's job is to hide infrastructure behind stable interfaces.

### Ray at Autodesk (kqI_YboaGXE)
**Speakers:** Victor (fine-tuning), Kong (inference). Autodesk Research.
**Platform (Ray Lab):** Researcher requests a project, not hardware. Workspace via JupyterHub. K8s namespace per project with RBAC. Ray on every stage: Ray Data (tokenize 3D geometry), Ray Train (fine-tune), Ray + Metaflow (eval orchestration), Ray Serve (multi-stage 3D generation).
**Fine-tuning on Trainium:** Qwen 3 (8B and 32B) on AWS Trainium 1 (trn1.32xlarge). 3 lines of code change from GPU: swap NCCL for TorchXLA config, GPUs for neuron cores, SFTTrainer for NeuronSFTTrainer.
**Key findings:**
- Sequence length is the cheapest knob to increase utilization and reduce cost
- Tensor parallelism sets the baseline of the utilization curve
- Trainium 1 becomes cheaper than H100 only for long training runs (high fixed startup cost from compilation)
- Best result: 14¢/million tokens for Qwen 3 8B LoRA on single node
- Weak scaling: 4 nodes → 3.47× speedup (not 4×); budget the scaling loss
**Inference on Inferentia 2:** Good for static-shape inputs (diffusion, ViT, CNN). Not competitive for autoregressive decoding (KV cache). Qwen 3 4B: comparable time-to-first-token at 80% of GPU cost at concurrency 200.
**Lesson:** Custom accelerators have hidden costs: observability wiring, memory budgeting, compilation caches, data staging. Budget the total cost of ownership, not just the hourly rate.

### Spotify Hendrix (XRHMqpTCeNM)
**Speakers:** Amir (Platform Engineer), Sean Lynn (Staff MLE)
**Platform (Hendrix):** Unified platform for AI/ML at Spotify. Multi-tenant GPU infrastructure across multiple GKE clusters/regions. >2× team growth in past year, 30× GPU compute hours increase, >1M GPU hours/month.
**Architecture:** Three-layer config: cluster config (GPU types, autoscaling, spot/reserved, worker groups), experiment config (metadata, overrides), training recipes (battle-tested defaults for attention, FSDP, DDP, masking). Hendrix SDK/REST API is the touchpoint. Kueue for admission control with DWS capacity provisioning. GCS Fuse for filesystem, MLflow + Cloud Logging for tracking.
**Key patterns:**
- **Composable workflows:** Data pipeline → training loop → evaluation. Each stage customizable. Ray Torch Trainer wrapped in envelope providing placement strategies, failure recovery, checkpointing. Teams can swap the training core via routing layer.
- **Heterogeneous clusters via sidecars:** Each runtime (training, inference, feature store) gets its own specialized image deployed as sidecar container. Ray host actor communicates with sidecar via network protocols. Trade-off: runtime independence vs serialization overhead.
- **Workload-initiated scaling:** Instead of utilization-based autoscaling, workload proactively scales worker pools up/down at phase boundaries. CPU workers up for data prep → GPU workers up for training → inference workers up for eval → release all. More efficient resource sharing across teams in same namespace.
- **Non-homogeneous inference:** Different engines for different task shapes — throughput-bounded ranking (attention mask API for inference-time packing), prefill-heavy with constrained decoding (stateful constraint decoding for semantic IDs), decoding-heavy (speculative decoding with draft model), miscellaneous/longtail.
**Lesson:** LLM recommendation models that speak both natural language and semantic IDs have fundamentally different inference characteristics per task shape. One inference engine doesn't fit all.

### Coinbase Migration (\_xLnyRFK54o)
**Speakers:** Akshhat, Aman (ML Platform team)
**Scale:** 50+ production models, >1B predictions/day in real-time user journeys (fraud, recommendations, compliance).
**Migration path:** SageMaker → self-managed Ray on EKS → Anyscale managed.
- SageMaker: slow iteration (sluggish Docker builds, boot times), dependency drift, config rework
- Self-managed Ray: Python-native, faster iteration, MLflow for artifacts. Single shared cluster with homogeneous workers.
- Shared cluster pain: noisy neighbor (recommendations spike starved fraud), single point of failure, GPU idle while CPU-heavy workloads ran, slow shared upgrades
- Anyscale: dedicated cluster per model domain (~20 clusters, 10 instance types, up to 500 nodes). Deployment via codified YAML + GitHub Actions. Canary + auto-rollback out of the box.
**Migration technique:** Serving gateway abstraction decoupled callers from backend. Shadow traffic to Anyscale → validate parity → swap primary → keep legacy warm → deprecate.
**Security model:** Anyscale control plane manages infra. Workloads run in Coinbase VPC — data/artifacts/dependencies never leave corporate network.
**Result:** Cluster management from weeks → minutes. Ray version upgrades trivial. Per-team cost attribution enabled team autonomy and accountability.

### Robinhood Heterogeneous Clusters (L9I2g6yh\_LA)
**Speakers:** Vira (AWS Solutions Architect), Robert (Robinhood)
**Platform (King's Cross):** Internal training platform abstracting infrastructure. Users submit via CLI → King's Cross job management → KubeRay provisions cluster.
**Evolution:** Ray libraries (single node) → KubeRay multi-node (contention for large instances) → heterogeneous clusters with multiple worker groups.
**Heterogeneous cluster pattern:**
- Worker groups with taints/labels: `cpu-only`, `gpu-small` (1×T4), `gpu-large` (A100), `gpu-train` (A100+NVLink)
- Karpenter node pools select right-sized instances per label
- Ray custom resources pin tasks to appropriate worker groups
- Independent autoscaling per worker group (CPU preprocessing scales separately from GPU training)
- Scale expensive hardware only when needed; scale to zero when idle
**Ray Data streaming:** Ray Data creates dataset → passed to Ray Train → streaming split distributes batches from CPU preprocessing workers to GPU training actors. Code works identically on single-node, homogeneous, or heterogeneous cluster.
**Results:** 67% cost reduction, ~4× runtime improvement. Higher GPU utilization by eliminating idle GPU time during CPU-heavy data preprocessing.
**Gotcha:** Cluster fragmentation — CPUs on GPU nodes may sit idle when all preprocessing is pinned to CPU-only workers. Straggler nodes during validation autoscale-up.
**Next:** Custom resource labels based on capabilities (VRAM amount, NVLink, FP8 support) instead of specific node types. Placement groups for RDMA collocation. Spot instances for fault-tolerant validation.

### Capital One KubeRay (MZFcNuYOch0)
**Speakers:** Marin (VP Product), Raja Shawat, Yi Wang
**Scale:** AI-first organization, ranked #7 in US AI patents. Massive sequence models processing 3.5TB training data with ~2B records.
**Pain:** Fragmented tools — siloed data processing, training, tuning, serving. Users managed disjointed codebases and dependencies. Inflated cost, impeded velocity.
**Solution:** Unified KubeRay ecosystem. Python-native, single programming model from prototype to multi-node GPU cluster. Zero infrastructure switching between ML lifecycle phases.
**Key results:**
- Ray Data streaming: 20× speedup over legacy pipelines. Lazy-loaded streaming from S3 through Ray object store to GPU memory on demand. Eliminated OOM crashes from loading multi-TB datasets into host RAM.
- Ray Train: 1.6× training speedup over vanilla PyTorch DDP. Zero-copy sharding from Ray Data to workers. Managed worker lifecycle with automatic rescheduling on failure.
- Ray Tune: 3× tuning velocity. 200 concurrent trials with ASHA early stopping. Per-trial GPU memory isolation prevents one bad config from crashing adjacent workers.
- Overall: 4× acceleration in model development lifecycle.
**Lessons:** K8s cold start is 3-5 minutes per GPU node — keep warm standby pods. Always set per-GPU memory limits during hyperparameter search. Never load multi-TB datasets into host RAM; use lazy streaming.

### Grab Platform (J31qKbcT5BA)
**Speakers:** Jong Yu (Intelligence Platform Lead), Ian (Senior Data Scientist), Abinav (ML Lead Engineer)
**Scale:** Super-app across 8 countries, 900+ cities. Mobility, food delivery, financial services.
**Three use cases on one platform:**
1. **Offline training:** World model (5.2B params, diffusion transformer, FSDP2 on 8×A100), cross-liver repost (DDP on 16 mixed GPUs), semantic ETA (140M params, DDP + Ray Data). Same Ray fabric for all — only topology YAML changes.
2. **Simulation parameter search:** Ray Tune + Optuna wrapping marketplace simulator. Each trial replays a full historical day (~3hrs). Engineer defines search space once; Ray manages trials, resources, failures. Eliminates human-in-the-loop scheduling bottleneck. Enforces guardrail constraints; penalizes unsafe configs.
3. **RL in simulator:** 30 parallel simulators (each replaying different historical date) collect trajectories → train policy → repeat. 30 days of market experience simulated in ~3 hours vs 30 days in production. Ray actors with `max_restarts=5` for fault tolerance; failure isolated per actor.
**Key patterns:**
- **Topology flexibility:** Same training code across 8×A100 single-node, 2×(4×A100) multi-node, 8×(1×A10G). Only YAML config changes. Memory policies configurable per hardware (keep gathered on A100, reshard on A10G).
- **Heterogeneous resource pools:** Training on powerful A100 pool, async validation on cheaper GPUs. Pools isolated so training never blocks validation.
- **Ray Data streaming for RL:** 600M+ trajectory records (~100GB) from 30 simulators. Streaming from S3 in micro-batches, local shuffle buffer for approximate shuffling without full materialization. Scales to billions of records.
**Vision:** Close the loop — simulation-trained policy → warm-start for real-data fine-tuning → simulation narrows search space for live A/B experiments. Standard simulator interface so any Grab team can plug in.

### Adyen Pretraining (S7rVHuaBVXY)
**Speaker:** Hanna van der Vlis, AI Research Engineer
**Scale:** ~120M payments/day, 3K TPS peak, <30ms P50 latency SLA. Trillion-scale payment history.
**Problem:** Traditional payment ML used XGBoost (tree-based). New approach: treat payment sequences like language — pre-train transformer on sequences of payments, fine-tune for downstream tasks (fraud, identity resolution, scripted attack detection).
**Infrastructure journey:** Notebooks + Argo workflows → Ray on-prem. Previously: PySpark kernel for data prep → materialize → switch kernel → train (single node, no multi-node). Now: Ray enables streaming HDFS → serialize → transform → train → log in one pipeline with multi-node training.
**Model architectures:**
- Language model approach (BERT-style): Serialize payment features as tokens, mask and reconstruct. Works but loses data structure and wastes context window.
- Hierarchical model: Two-layer transformer — intra-payment attention (shared across all payments) → inter-payment attention (across sequence). Preserves structure, more context-efficient. Outperforms language-based approach.
**Key learnings:**
- Random masking too easy with correlated tabular features — increase masking % or mask correlated features together
- Fourier embeddings for amounts (captures both order of magnitude and round-number patterns)
- Sinusoidal encoding for relative time intervals between payments (critical for fraud detection)
- Byte-level + convolutional encoding for text features (patterns matter more than semantics for fraud)
**Results:** 3× more scripted attacks detected, 170% ARI uplift for identity resolution, 3% AUC uplift for fraud. Developer happiness "increased a lot."
**Lesson:** In tabular/payments ML, how you represent the data matters more than the model architecture. Most experimentation is in encoding and preprocessing, not the transformer itself.

---

## Cross-Cutting Patterns

### Migration Playbook (Observed Across Talks)
1. **Start with offline workloads** — training/batch inference migrate first (lower risk)
2. **Use a gateway/abstraction layer** — decouple callers from backend (Coinbase serving gateway, BMW LiteLLM proxy)
3. **Shadow traffic** — run new platform in parallel, compare metrics
4. **Swap primary, keep legacy warm** — rollback safety net
5. **Deprecate legacy** — only after confidence period

### Platform Team Size vs Scope
| Company | Team size | Scope |
|---|---|---|
| Lila Sciences | ~15 | Multi-cluster, multi-cloud, multi-region |
| Discord MLP | Small (grew from "actual picture of us") | Single cloud, full training + serving |
| Recursion ML Infra | Small team | Hybrid cloud + on-prem, batch + online |
| BMW Connected AI Platform | 35+ engineers, 6 teams | Enterprise-wide AI gateway + training |
| Spotify Hendrix | Not stated but implied large | Multi-region GKE, >1M GPU hours/month |

### Self-Hosted vs Managed API Decision Matrix
| Factor | Self-host | Managed API |
|---|---|---|
| Data privacy required | ✓ | ✗ |
| High-volume / high-token usage | ✓ (flat GPU cost) | ✗ (linear token cost) |
| Latest frontier model needed | ✗ | ✓ |
| Operational capacity for serving | Required | Not required |
| Predictable cost | ✓ | ✗ (usage-dependent) |
| Time to first deployment | Slower (ops setup) | Faster |

### Heterogeneous Cluster Adoption Criteria
Use heterogeneous clusters when:
- Jobs have distinct CPU-heavy and GPU-heavy phases (Robinhood: preprocessing → training)
- Different workload phases need different dependencies/images (Spotify: training vs inference vs feature store)
- Validation can run on cheaper GPUs than training (Grab: async validation on A10G while training on A100)
- You want to scale expensive hardware only when needed (Robinhood: GPU workers scale to zero during preprocessing)

Do NOT use when:
- Single-phase GPU-only workloads (simpler to use homogeneous)
- Team lacks observability to identify the phase boundaries
- Job is short enough that autoscaling overhead exceeds savings
