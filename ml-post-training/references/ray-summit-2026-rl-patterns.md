# Production-Scale RL Patterns from Ray Summit 2026

Extracted from 13 conference talks on real-world RL training at scale. These patterns complement the core SKILL.md content with infrastructure and systems-level concerns that emerge at 100+ GPU production deployments.

**Sources**: Ray Summit 2026 talks from NVIDIA, Microsoft AI, RadixArk/Anyscale, Lila Sciences, Google, AWS, Lambda, Mercor, Prime Intellect, Torc Robotics, SonderMind, and Inception Labs.

---

## 1. Async RL Training Loop Architectures

### The Problem with Synchronous RL

Synchronous RL has two taxes at scale: (1) **long-tail stragglers** — a batch of 512 rollouts will have a few that take many turns and stall the entire trainer, and (2) **bubble time** — switching between rollout and training phases leaves GPUs idle during the other phase. Both waste compute proportional to cluster size.

### Fully Async RL (Miles, SkyRL)

The dominant production pattern is fully async: rollout and training run independently, neither blocking the other. Key implementation details:

- **Sample-level scheduling**: schedule at individual sample granularity, not batch level. When an inference slot frees, immediately fill it with the next sample. This eliminates batch-level straggler blocking.
- **Bounded version buffer**: log the weight version of each trajectory. A data buffer accumulates completed trajectories and decides whether each is fresh enough to train on (bounded staleness). Back-pressure prevents the buffer from growing unbounded.
- **In-loop weight update**: when a training step finishes, update inference weights immediately rather than waiting for all rollouts to complete. Delta updates (sending only changed weights) complete in seconds even at trillion-parameter scale.
- **Generation-bounded operation**: the training engine should never be idle waiting for data. The metric to watch in SkyRL is "wait for generation buffer" — if it's nonzero, add more inference capacity.

*Source: Miles (5ohCn8lLwds), SkyRL (LR947BdMdO4), Lila Sciences (Zln7cKS75WY)*

### Async RL at Microsoft AI (MAI-Thinking-1)

Microsoft AI runs RL across multiple Ray clusters (up to 32K workers) using a RELAY batch proxy architecture:

- **Relay actors**: vanilla Ray actors deployed per Ray cluster that take batched RPCs from a single training driver and fan out locally. This decouples the driver from per-cluster GCS overhead.
- **Relay tree**: beyond 8K actors, a flat relay topology bottlenecks on the driver CPU. A tree hierarchy of relays maintains O(S) complexity at the driver (S = number of clusters) while scaling to 32K+ workers with <200ms P50 RPC round-trip time.
- **Partial restart over cold boot**: when a failure occurs, restart only the affected component (e.g., learner only, not the entire job). This preserves inference state and avoids multi-minute Kubernetes pod scheduling.
- **Scheduling actor**: a Ray actor maintaining a global view of all node resources (learner pool, inference pool, spare pool, bad-node pool) with a simple get/return/report-bad interface. Designed to fail fast so requesters can retry.

*Source: Microsoft AI (7fCwq7pIrkA)*

### Sticky Least-Loaded Routing (SkyRL)

For multi-turn agentic RL, consistent hashing routes all turns of a trajectory to the same VLM replica (maximizing prefix cache reuse) but creates load imbalance when some trajectories take 50+ turns. **Sticky least-loaded** routing sends new trajectories to the replica with the fewest active requests, then pins subsequent turns to that same replica. Measured 1.4x generation throughput improvement on a 350B MoE model.

*Source: SkyRL (LR947BdMdO4)*

---

## 2. Weight Sync Patterns

### The Evolution of Weight Transfer

Weight sync is the critical path between training steps and inference freshness. Three generations:

1. **NiCCL broadcast** (baseline): single trainer rank broadcasts full weights to all inference ranks. Every worker receives the entire model even if it only needs a shard. A single straggler stalls the collective. Does not scale past ~100B parameters without unacceptable delays.

2. **P2P via Mooncake** (Microsoft AI contribution to Miles): leverages all TP workers on the trainer for peer-to-peer transfer. Faster than broadcast, but requires loading the entire model to CPU first, which breaks on transports that don't support CPU offloading (e.g., EFA on AWS).

3. **RDMA via Ray Direct Transport (RDT) + NIXL** (current best): zero-copy GPU-to-GPU transfer. Ray manages memory registration and internal memory pools, grouping small tensors to minimize registration overhead. On bare-metal GB200 with NVLink, achieves ~859 GB/s (vs. theoretical 900 GB/s). No CPU replica needed, no over-registered memory, auto-discovers inference engines by name. For Kimi K2 (1T parameters), completes weight sync in 7.53 seconds across 48 H100 nodes.

*Source: Miles (5ohCn8lLwds), SkyRL (LR947BdMdO4), NVIDIA (mgZXBf_nrQg)*

### Delta Weight Updates

Instead of syncing the full model, compute and transmit only the difference between consecutive training steps. Combined with RDMA, this reduces weight sync to seconds even at trillion-parameter scale.

*Source: Miles (5ohCn8lLwds)*

### NVIDIA Transfer Queue

At trillion-parameter MoE scale with 128K sequence lengths, rollout data can reach 10 GB/step for standard rollouts, 50 GB for on-policy distillation (top-8 logits), and 268 GB with routing replay. NVIDIA decoupled control plane from data plane using a Transfer Queue backed by CPU memory or GPU-direct RDMA:

- Transfer Queue alone: 2–4x throughput improvement
- Adding RDMA: additional 2–3x, with dramatically reduced variance
- GPU-direct RDMA is ~2x faster than CPU RDMA

*Source: NVIDIA Nemotron (mgZXBf_nrQg)*

---

## 3. Token-Level Correctness (TiToR and Routing Replay)

### The Token Drift Problem

In multi-turn agentic RL, tokens pass through detokenization (to strings for sandbox execution) and retokenization (back to token IDs for training). This round-trip can change the token sequence even when the string is identical. Example: tokens [0, 1, 3] → string "[search]" → retokenized as [2, 3] where token 2 is "bracket+search". The trainer then computes gradients on tokens the policy never emitted — an off-policy error that compounds across turns.

### Token-In Token-Out (TiToR)

A middleware session server sits between the inference engine and the sandbox. It:
1. Records the exact output token IDs, log-probs, and routed experts for each turn
2. Appends to a persistent session (not re-tokenizing from strings)
3. Sends exact token IDs to the trainer

The trainer scores exactly what the policy emitted, by construction. Three implementation approaches:
- **Rewrite harness to use completions API** (token-space throughout) — most control, what Mercor used
- **Use `return_token_ids`** in VLM chat completions — low effort, but doesn't solve multi-turn concatenation
- **Proxy in RL framework** that translates chat completion to completion API while bookkeeping tokens — coming to SkyRL

*Source: Miles (5ohCn8lLwds), Lila Sciences (Zln7cKS75WY), Mercor (eu1R58lqfDc)*

### R3: Rollout Routing Replay

For MoE models, floating-point non-associativity means training and inference kernels can reduce in different orders, producing slightly different router logits. Even one digit of difference can flip expert selection in sparse routing, causing completely different weight paths. **R3** records the expert selections during rollout and replays them during training, eliminating router-flip mismatch.

**Scale challenge**: routing replay data grows as `tokens × top_K_experts × layers`. At large scale this can be 100+ GB arrays in RAM. Mitigations that Lila Sciences stacked:
- Lower-precision integers for expert indices
- Sequence packing on metadata (no padding waste)
- Binary encoding for network transfer (not JSON character encoding)
- Careful Ray object store sizing (avoid disk paging)
- Eliminate Python list operations on multi-GB arrays; use vectorized operations

*Source: Miles (5ohCn8lLwds), Lila Sciences (Zln7cKS75WY), SkyRL (LR947BdMdO4)*

### Top-P Sampler Replay

Captures the exact token IDs included in the top-P set during inference and replays them during training for consistent renormalization. Empirically, >50% of tokens have a single token at >95% probability mass, so sparse representations drastically reduce data volume. PyTorch sparse tensor operations speed up loss computation.

**Combined effect**: R3 + top-P replay enables stable long RL runs (100+ steps) with maintained entropy and continued reward climbing, whereas runs without these features can destabilize and collapse.

*Source: Lila Sciences (Zln7cKS75WY), SkyRL (LR947BdMdO4)*

### Zero KL RL Training

SkyRL achieved batch-invariant zero train-inference mismatch between VLM and Megatron by defining a unified execution framework, with only 20% throughput slowdown. After kernel alignment and reduce-order matching, KL divergence drops to numerical noise in true on-policy settings.

*Source: Miles (5ohCn8lLwds), SkyRL (LR947BdMdO4)*

---

## 4. Reward Engineering Patterns

### Reward Stress Testing (Prime Intellect)

Before optimizing against a verifier thousands of times, validate that the verifier is worth optimizing. A systematic stress-testing workflow:

1. **Controlled fault injection**: inject simple mechanical mutations (flip comparisons, negate booleans, shift boundaries, swap arguments, reverse sort order) into code repositories. You know the exact repair (reverse the mutation), giving verifiable tasks without LLM judges.

2. **Test coverage audit**: run mutations across real repositories and check if existing test suites catch them. Result: miss rates span 0–90% across repositories; roughly half of injected faults are invisible to existing tests. If tests can't distinguish buggy from correct state, reward functions built on those tests can't either.

3. **Scorer isolation**: run the scorer in a hardened path with strict access controls. With isolation on: 0 false positives out of 240 rollouts. With isolation off: 58 false positives (24%). One model went from 67% verified solve rate (accurate) to 98% reported (inflated) when scorer isolation was disabled.

4. **Red-team the verifier with unit tests**: construct cases with known expected verifier behavior. Found 2/5 unit tests failing even on "simple" verification logic.

5. **Best-of-N amplification test**: if the verifier has false positives, best-of-N selection amplifies them. With a broken scorer, reported success rate climbs monotonically with N even though actual success doesn't.

6. **Trajectory-level analysis**: outcome-only rewards catch 0% of process-level hacks (e.g., agent reading planted answer keys). Trajectory-level agent judges caught 73% of process hacks. Essential as tasks become longer-horizon.

**Key finding**: reward hacking behavior is model-dependent and non-uniform. Different model families exploit different weaknesses at different rates. Blanket assumptions about hack rates don't hold.

*Source: Prime Intellect (nB1p_3Bhj2Y)*

### Reward Function Design for Agentic RL (Mercor Playbook)

A 6-step playbook for hill-climbing on agentic benchmarks:

1. **Environment robustness** (no RL yet): run 600+ concurrent rollouts and verify near-zero infrastructure errors. Add timeouts to everything (snapshot downloads, MCP calls, container teardown). Don't share Python event loops across concurrent agent processes.

2. **Harness optimization**: do an eval pass on all data, use a coding agent to audit why trajectories failed. Fix harness quirks before RL — otherwise the model learns to work around bugs rather than genuine capability. Mercor improved mean reward from 23% to 28% (without any training) just by fixing tool bugs (PowerPoint returning None on success, pip install failures, PDF flattening 2D tables to 1D, tool responses blowing context windows).

3. **Overfit on a subset**: pick 32 tasks, synchronous RL, one epoch per step. If you can't overfit, you won't succeed at scale. This catches grading bugs (e.g., noisy verifier due to unfaithful file-diff tool).

4. **Ablate algorithmic knobs on a small model**: the knobs that mattered most for Mercor:
   - **Loss aggregation**: prompt-mean vs. token-mean — prompt-mean gave +4 absolute points (biggest single knob)
   - **Context nudge**: nudge model to finish when 80% of context consumed — +3 points (more sequences complete, more learning signal)
   - **DPPO vs. standard policy loss**: similar performance but DPPO learned more exploratory behavior (more turns, shorter reasoning)
   - **Overlong filtering and length penalty**: neutral to negative — don't use

5. **Hero run**: same recipe, bigger model. Only change is re-tuning Megatron parallelism knobs for the larger model.

6. **Generalization study**: verify RL gains transfer across harnesses. Mercor's 35B model transferred almost completely from Archipelago (MCP-based) to OpenCode (bash-only). 397B transferred partially. The 35B model shifted toward more code execution over MCP tools during training, which explained better transfer.

*Source: Mercor (eu1R58lqfDc)*

---

## 5. Topology-Aware Placement

### NVLink Domain Placement (NVIDIA)

Ray's default scheduler has no awareness of NVLink switch domains. For MoE expert parallelism, if actors spread across racks, the all-to-all collective crosses InfiniBand instead of staying within the NVLink domain. NVIDIA implemented explicit NVLink domain-aware placement: expert parallelism actors allocated within a single rack. Result: **20% end-to-end throughput improvement**.

### NUMA-Local Binding (NVIDIA)

On GB200 (2 Grace CPU sockets, 4 Blackwell GPUs per compute tray), a Ray worker scheduled for GPU 0 might land on socket 1 cores. All data offloading then crosses the inter-socket coherence link instead of NVLink C2C (~1 TB/s bidirectional, only available between GPUs and their local sockets). Fix: on `ray.init`, probe topology, map GPU→local socket, pin worker to that NUMA node (CPU affinity + memory). Result: **10% end-to-end throughput improvement**.

### Explicit Node Assignment (Microsoft AI)

For large-scale RL with heterogeneous components (learner needs NVLink-64, inference needs NVLink-16, sandbox needs CPU), Microsoft AI bypasses Ray's default scheduler entirely. A scheduling actor maintains the global resource view and assigns specific IPs to actors. Benefits: topology-aware placement, easy actor collocation (inference router + inference server on same node), explicit capacity control with spare-node pools.

*Source: NVIDIA (mgZXBf_nrQg), Microsoft AI (7fCwq7pIrkA)*

---

## 6. RL on Custom Silicon

### TPU as First-Class Ray Accelerator (Google)

Starting with Ray 2.55, TPUs are a tier-one accelerator with official CI/CD testing — the only accelerator besides GPUs to achieve this. Practical implications:
- Request TPUs via standard `@ray.remote(num_gpus=...)` decorator (same API as GPUs)
- TPU metrics (duty cycle, memory) pipe into the standard Ray dashboard
- Pre-packaged TPU Docker images with verified dependencies
- To switch SkyRL from GPU to TPU: change Kubernetes node selector, swap container image, same `ray job submit` command. Zero application code changes.

**Reference architecture**: GKE at bottom managing TPU/GPU accelerators → Ray as universal orchestrator → ML frameworks (Jax, PyTorch) at top. Infrastructure teams manage GKE + Ray; ML researchers choose frameworks freely.

*Source: Google (nwdh1wEKing)*

### Trainium Integration (AWS)

AWS Trainium slots in below Ray's worker interface with minimal changes:
- The device is `"neuron"` instead of `"cuda"`, process group backend is `"neuron"` instead of `"nccl"`, compiler backend is `"neuron"` instead of `"inductor"` — three string changes
- VOWL recipe change: add `device="neuron"`. Same GRPO hyperparameters, same training loop
- Multi-node scaling: standard Ray head/worker setup, `ray job submit`
- Validated: same learning curve shape as H100 baseline, up to 1.7x faster in some cases
- Static shape enforcement for ahead-of-time compilation: fixed KV cache, fixed padding, chunk prefill. Trace two shapes (chunk prefill + single token decode), reuse throughout

*Source: AWS (RtEPrSrryQY)*

### GPU Time-Slicing for RL (Google/LLMD)

RL workloads typically utilize only 40–60% of accelerators due to train/sample phase gaps. **Time-slicing** multiplexes multiple RL (or RL + non-RL) jobs on the same GPUs:
- Three-layer architecture: workload layer (tag jobs as train/sample), accelerator orchestrator, snapshot agent (checkpoint job state to host memory for fast context switching)
- Result: 66% fewer GPUs for the same 3-job workload, 30% faster than sequential execution on 2 GPUs, no quality compromise
- Recipes available in the open-source LLMD project for Slime, SkyRL, NeMo RL, and others

*Source: Google (nwdh1wEKing)*

---

## 7. Simulation-RL Unification Patterns

### Autonomous Trucking at Scale (Torc Robotics)

Torc runs >1 billion miles of simulation per week using a unified sim+RL architecture:

- **Three RL styles**: ego-only (replay log, train ego policy), self-play (all agents share one policy), mix-play (mixture of log-replay and self-play agents)
- **Scenario flywheel**: fleet recordings → auto-labeling pipeline finds interesting scenarios (cut-ins, hard braking) → vary parameters (speeds, positions) → build scenario cache → train + simulate → evaluate on held-out test → mine for new failure scenarios → repeat
- **Mid-level representation training**: CPU-vectorized simulator (buffer-drive) on CPU cores, GPUs reserved for learning only. Achieves 2 billion steps in 40 minutes on 6 GPUs, 1M steps/second on 8 H100s. Bottleneck is the model, not the simulator.
- **Torque Nerve**: a modular graph execution engine built on Ray that supports arbitrary operator topologies (linear, fan-out/fan-in, loops for closed-loop evaluation). Separates operators, graph topology, and execution environment so the same graph can run locally on Ray Core or at scale on Anyscale.
- **Rollout engine decoupled from RL harness**: the rollout engine (Nerve) is independent of the RL training harness (VOWL, SkyRL, RLlib). As long as the harness is Ray-based, they compose. This protects against RL framework churn.

*Source: Torc Robotics (BI2tCELCnmI)*

### Physical Simulation RL (Lambda)

Humanoid locomotion fine-tuning with Isaac Sim on 16 B200 GPUs:
- 512 environments per GPU (8,192 total), 139K environment steps/second
- Headless physics-only simulation (no camera rendering) — enables running on GPUs without ray tracing
- Each GPU does both environment generation and gradient computation; weights only aggregate during updates (minimizes CPU↔GPU bandwidth)
- **Reward design for physical RL**: penalize non-humanoid gaits (joint speed limits, leg speed, time with feet in air), mix easy and hard environments for smoother learning curves, use KL divergence toward original policy to prevent the robot from "cheating" (e.g., walking on all fours)
- Fall rate improved from 4.75% to 0.78% while travel distance also improved (verifying the robot didn't just learn to stand still)

*Source: Lambda (h5WslH8dFkM)*

---

## 8. Diffusion LLM RL

Diffusion LLMs (Mercury from Inception Labs) require rethinking RL because standard log-likelihood computation is intractable — it requires integration over exponentially many masking patterns. The solution:

- **Mean field approximation**: compute log-likelihoods by sampling masked positions and treating them as independently unmasked. One forward pass per estimate. Low variance, efficient.
- **Better exploration**: same inference sample can be reused with different input masks, yielding multiple gradient steps without additional inference cost. This reduces the key RL bottleneck (inference throughput).
- **RL scaling benefit**: 3–5x improvement in post-training scaling law due to faster inference engine. Can generate larger GRPO groups in the same time, or do more gradient steps with the same group size.

*Source: Inception Labs (3aFgZJNj7eg)*

---

## 9. Control Plane Scaling (3K+ GPUs)

### GCS Bottleneck at Scale (NVIDIA)

At 3K GPUs with ~10K GCS registrations, Ray cluster initialization took 33+ minutes due to thundering herd on the head node. Mitigations in order of impact:

1. **Reduce actor count**: audit actors, convert short-lived actors to tasks, consolidate initialization actors per node (42% reduction in GCS registrations). Move static models (judges, reward models) behind persistent endpoints (20% init time reduction). Disaggregate sandboxes to their own cluster (30% reduction).
2. **GCS event loop fix** (in Ray 2.55+): Anyscale moved GCS node manager and KV manager to their own IO contexts, freeing the main event loop from CPU-bound work.
3. **Config tuning**: increase GCS thread pool, increase registration/connection/reconnection timeouts, reduce background chatter intervals, add jitter to actor registrations, stagger initialization batches.
4. **Head node isolation**: set zero schedulable resources on head node so it does orchestration only. Prevents resource contention that causes cascading heartbeat failures.
5. **Durable GCS state**: checkpoint cluster metadata to durable storage for fast reload on head node failure.

Final result: cluster initialization under 3 minutes (down from 33+).

*Source: NVIDIA (mgZXBf_nrQg)*

### Port Contention Fix

Ray's probe-and-release port allocation pattern creates a race window where other cluster services can grab the port. Fix: pin Ray internal worker ports to the non-ephemeral band; ephemeral ports used for everything else.

*Source: NVIDIA (mgZXBf_nrQg)*

---

## 10. Domain-Specific RL

### Clinical Mental Health (SonderMind)

LoRA fine-tuning on real therapy session data (with deep anonymization) to make LLMs more therapeutically aligned:
- **Multiple LoRA adapters per modality**: CBT, DBT, motivational interviewing, psychodynamic therapy — served dynamically based on user preferences
- **Eval suite for clinical RL**: MindEval (clinical quality), VeraMH (safety), adapted CTRS scale (human therapy rating scale for AI), sycophancy evaluations, memorization checks for data privacy
- **Mechanistic interpretability for safety**: replicated Anthropic's persona vectors technique to verify that fine-tuned model shows reduced activation in sycophancy-associated parameter space during mental health conversations
- **Key finding**: fine-tuned model draws on 98 therapeutic techniques (vs. 68 for base) while staying consistent within a single modality per session — clinically important for patient continuity

*Source: SonderMind (jNSjjduRhS0)*

---

## 11. FP8 RL Training

SkyRL validated stable FP8 mixed-precision RL:
- FP8 on trainer for faster matrix multiplications
- FP8 model weights on inference side for faster decode (memory-bandwidth bound)
- FP8 KV cache for higher concurrency
- **On-policy FP8 weight sync**: sync exact FP8 quantized weights from Megatron to VLM (not re-quantize after transfer). Achieves lower log-prob mismatch than naive quantization.
- Keep precision-sensitive tensors (e.g., router logits) in BF16
- Speedups: ~20% on Qwen 3.5 9B (single H100), ~23% on Qwen 3.5 35B (single B200)

*Source: SkyRL (LR947BdMdO4)*

---

## 12. Fault Tolerance Patterns

### Spare Capacity + Hot Swap (Microsoft AI)

Jobs specify both required racks and spare racks. On failure:
1. Diagnostics actors (Ray actors wrapping GPU health checks via nvidia-smi/NVML, kernel logs, Ray logs) run fast checks to identify unhealthy racks
2. Unhealthy racks swapped with pre-warmed spare capacity
3. External component maintains spare rack count, replacing unhealthy racks asynchronously
4. Pre-warmed actors on spare capacity avoid cold-boot latency

### Fast Error Detection (Microsoft AI)

Deep errors in complex RL systems can lose detail as they propagate through library layers. An **error actor** allows any library/component to directly propagate fatal errors to the controller, bypassing intermediate error handling that might mask root causes.

### Liveness Monitor (Microsoft AI)

A periodic actor that scans all actors against configurable rules (e.g., "any learner failure → immediate restart", "inference workers below threshold → restart"). Eliminates waiting for timeouts.

*Source: Microsoft AI (7fCwq7pIrkA)*

### Fault-Tolerant Weight Sync (SkyRL + NIXL)

Sharded peer-to-peer weight transfer via NIXL enables continued training even if an inference replica fails — no need to tear down the entire collective communication group (unlike NiCCL broadcast).

*Source: SkyRL (LR947BdMdO4)*

---

## Quick Reference: Which Talk Covers What

| Pattern | Primary Source |
|---|---|
| GCS scaling at 3K+ GPUs | NVIDIA Nemotron (mgZXBf_nrQg) |
| RELAY tree for 32K workers | Microsoft AI (7fCwq7pIrkA) |
| Fully async RL + TiToR + R3 | Miles/RadixArk (5ohCn8lLwds) |
| R3/top-P at scale engineering | Lila Sciences (Zln7cKS75WY) |
| SkyRL architecture + FP8 + weight sync | Anyscale SkyRL (LR947BdMdO4) |
| 6-step RL playbook | Mercor (eu1R58lqfDc) |
| Reward stress testing | Prime Intellect (nB1p_3Bhj2Y) |
| TPU reference architecture | Google (nwdh1wEKing) |
| Trainium RL integration | AWS (RtEPrSrryQY) |
| Diffusion LLM RL | Inception Labs (3aFgZJNj7eg) |
| Physical simulation RL | Lambda (h5WslH8dFkM) |
| Sim-RL unification (1B miles/week) | Torc Robotics (BI2tCELCnmI) |
| Domain-specific clinical RL | SonderMind (jNSjjduRhS0) |
