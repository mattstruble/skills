# Ray Summit 2026 — LLM Inference & Serving Patterns

*Extracted from 14 talks at Ray Summit 2026. Organized by theme with concrete production numbers.*

---

## 1. Parallelism & Model Sharding

### Custom Pipeline Parallelism for Parallel Track Transformers (Apple)
[dETUxz8bsB8](https://www.youtube.com/watch?v=dETUxz8bsB8)

- **Parallel Track Transformer (PTT):** Standard transformer shortened into independent tracks on separate GPUs. Tracks join via single all-reduce every D layers instead of 2 all-reduces per layer. Cuts collective communication from 2L to L/D.
- **Mapping to vLLM:** Tracks → TP axis; pipeline stages → PP axis. No new communicator — reuses vLLM's existing NCCL communicator.
- **Plugin architecture:** PTT registers via vLLM plugin system. No engine fork. Scheduler, paged KV cache, continuous batching, chat completion API all work as-shipped.
- **Ray compiled DAG deadlocks:** First inference triggers lazy DAG compilation for NCCL channels. Cyclic stage dependencies caused deadlocks. Fix: bypass compiled DAG entirely; use Ray actor mailbox dispatch (FIFO) with `torch.distributed.send/recv` for activations.
- **CPU metadata transfer bottleneck:** NCCL activation transfer was microseconds, but tensor metadata sent via CPU gloo calls cost 70ms–2s tail latency. Fix: cache tensor metadata per CUDA graph capture size. Send only the size index over NCCL.
- **GPU-CPU synchronization bottleneck:** Reading NCCL index tensor via `.item()` triggered CUDA synchronize (~20ms). Fix: speculate the batch size from vLLM scheduler output and fit to next CUDA graph capture size. Kept synchronization as fallback.
- **Combined improvement:** From low TP32 baseline to significantly higher generation throughput through PP + custom MoE kernel + CUDA graphs + NCCL index caching + speculative receive.

### Serving DeepSeek V4 on B200s (Nscale)
[bgem5_ooJqk](https://www.youtube.com/watch?v=bgem5_ooJqk)

- **DeepSeek V4:** 284B vision params, 13B active per token. Sparse MoE. Native 1M token context. CSSA+HCA compression saves 90% KV vs. V3.2. Ships with FP4/FP8 quantization and DSpark speculator built-in.
- **Hardware:** 3× B200 nodes (8 GPU each) on Nscale Kubernetes cluster in Norway.
- **Strategy comparison (32 concurrent requests):**
  - TP + EP: ~2,200 aggregate tokens/s (fastest)
  - DP + EP (DeepSeek reference): ~1,600 tokens/s (most consistent)
  - DP + EP + speculative decoding: ~300 additional tokens/s
  - Replicas (DP only): ~2× of strategy B
  - P&D disaggregation: measured ~1,700 tokens/s but **output was junk** (engine version bug)
- **Critical lesson:** Always validate output quality, not just throughput. Different vLLM versions produce different results — one version was 45% slower, another produced garbage output for simple prompts.
- **Long context:** 1M token context works but a needle-in-haystack test takes ~60 seconds. Cap `max_model_len` to prevent resource hogging. Use FP4 indexer for context compression.
- **Config is architecture:** Engine args (parallelism, quantization, speculative decoding, max length) fundamentally change model behavior. Test every combination with specific engine version.

### MoE at Lowest Cost — GB300 NVL72 (NVIDIA)
[FCtTk4H8ynM](https://www.youtube.com/watch?v=FCtTk4H8ynM)

- **Model growth:** 25,000× since BERT (110M → 3T parameters). 7× annual growth rate. Capabilities growing 15× (2× prior year rate).
- **MoE communication cost:** DeepSeek V3 (256 experts, 9 active per token) dispatch+combine payload up to 20MB per token. Agentic workloads compound this: 100 turns/request, 100K token context, 15× more tokens than chat.
- **GB300 NVL72:** 18 trays × 4 GPUs = 72 GPUs. Copper cable spine via 9 NVLink switch trays. Each GPU: 1,800 GB/s. Total: 130 TB/s all-to-all. Eliminates MoE dispatch bottleneck. Compare: Hopper 8-GPU node scaling via Ethernet at 100 GB/s = ~5% of NVL72 bandwidth.
- **Performance:** Hopper → Blackwell: 20× on real agentic workloads (semi-analysis AgentX benchmark). Vera Rubin: 30× on top of Blackwell.
- **Cost:** Blackwell delivers tokens at 1/10th the cost of Hopper despite higher rental cost.
- **Dynamo integration with Ray:** KV indexer for cache-aware routing. NVLink group awareness in Ray placement groups — places GPUs in same rack for 130 TB/s instead of spreading across racks.
- **Software stack layers:** Production ops (Dynamo: disaggregated serving, KV routing) → Application (TensorRT-LLM: kernel fusion, spec decode) → Infrastructure (CUDA, NCCL). Optimizations compound across layers.

---

## 2. Speculative Decoding

### vLLM Leaderboard — Eagle + Kernel Fusion (DigitalOcean)
[Cd-3H6XdAyE](https://www.youtube.com/watch?v=Cd-3H6XdAyE)

- **Hardware:** B100 GPUs (50% more memory than B200 prior gen; 1.5× NVB4 compute).
- **NVB4 quantization:** 1.8× less memory footprint. Less data movement → faster TPOT. Minimal accuracy loss (GPQ/diamond benchmarks).
- **Kernel fusion:** Attention path has many small kernels (RMSNorm, RoPE, FP8 quant). Fused 33 kernel launches → 10. Eliminates repeated main memory round-trips; uses register/shared memory. 1.2× speedup. Also fused DeepSeek sparse attention (DSA) path.
- **Programmatic dependent launch (PDL):** Overlap dependent kernel launches. Reduces kernel launch time in decode path.
- **Speculative decoding for MiniMax/Qwen:** Trained custom Eagle model with hidden states from MiniMax for better acceptance rate. Combined with PDL for leaderboard results.
- **Results:** TPOT: 7–8ms → 4ms. Output speed: 230+ tokens/s. Top of Artificial Analysis leaderboard for DeepSeek 3.2.
- **All open source:** Recipes available in vLLM. No closed forks.

### Slim Spec + Disaggregated Quantization (Nebius)
[hwZfXCYgWNQ](https://www.youtube.com/watch?v=hwZfXCYgWNQ)

- **Kernel Design Agent (KDA):** Automated loop: planning (with kernel wiki of prior designs) → candidate generation → NCU profiling → production validation → contribute back to wiki. 8× speedup on DeepSeek sparse attention kernel vs. FlashInfer.
- **Spec decoding candidates:** Eagle, DSpark, Slim Spec. All lossless.
- **Slim Spec:** LM head (embedding → vocabulary projection) is 50–60% of drafter latency for many models. Insert low-rank bottleneck between embedding and vocabulary layers. At 1/8 embedding size: 5× speedup on LM head layer, 0.99 acceptance length retention. 10% real production speedup. Orthogonal to Eagle/DSpark — can combine.
- **Disaggregated quantization:** Prefill = compute-bound (algorithm intensity >100). Decode = memory-bound (intensity ~1.3). Use FP16 for prefill KVs (reused by every decode token) + W4A4/W4A16 for decode. Result: 2.3–2.5× decode speedup, 2.3× E2E speedup, full FP16 accuracy recovery.
- **Vera Rubin / Groq LPX:** Experimenting with disaggregated precision on new hardware. LPX for low-precision decode, FP16 prefill on main GPU. Co-design hardware features with model precision.
- **Production tuning:** Continuously retune speculators with real customer traffic. Reprofile kernel bottlenecks under production load. Ever-changing SLAs/SLOs require adaptive optimization.

### DSpark Training at Scale (Red Hat / Speculators)
[K6FddIlAIOk](https://www.youtube.com/watch?v=K6FddIlAIOk)

- **Speculators project:** Production training library under vLLM ecosystem. 33 published drafters in Red Hat AI collections. 6 algorithms: Eagle-3, D-Flash, DSpark, PGO, MTP, D-Flash 2.
- **DSpark vs. Eagle:** Eagle autoregressive (3–5 tokens/step). DSpark: diffusion-based, one forward pass, 8–16 tokens/step. Markov head recovers causal relationships with low-rank bias. Confidence head + prefix tree trimming skip low-confidence tokens.
- **Kimi K3 DSpark recipe:** 48 GB300 GPUs across 12 nodes. 4× TP8 independent Kimi K3 extractors (vLLM). DP16 replicated DSpark trainer on 16 GPUs. Two epochs. Final validation acceptance length: 4.15. "Best on the market."
- **Hidden states extraction:** Drafters learn verifier's "inner thoughts" (hidden states) not just tokens. vLLM natively supports hidden state extraction — smuggles them out dressed as KV cache (layer→num_heads, hidden_size→head_size mapping). Zero extra allocation.
- **MoonCake connector for multi-node:** Original connector used shared storage (single-node only). MoonCake: trainer sends request → extractor returns data handle + metadata → MoonCake master fetches tensor. Enables cross-node streaming.
- **GB300 NVL72 architecture:** 72 Blackwell GPUs in 18 trays. 4 training units: 2 trays extractors + 1 tray trainer each. Target and drafter fully disaggregated. Only hidden states cross node boundaries + tiny gradient all-reduce across 16 trainer GPUs.
- **Profiling insight:** Majority of time spent waiting for hidden state extraction. Training itself is negligible. Future: more vLLM replicas, more KV headroom, optimize data loader workers.
- **vLLM drafter serving:** Async scheduling (step N+1 prepared while step N runs). Full CUDA graph for draft step — zero per-launch overhead for tiny drafter.

---

## 3. KV Cache & Long Context

### KV Cache Offload to Networked Storage (VAST Data)
[h5hVWBPAP8A](https://www.youtube.com/watch?v=h5hVWBPAP8A)

- **Core thesis:** KV cache is becoming long-lived memory. Performance depends on management efficiency, not just GPU compute.
- **Dynamo memory hierarchy:** G1 (GPU HBM) → G2 (system RAM) → G3 (networked storage, current integration) → G3.5 (local SSDs via BlueField DPU, upcoming) → G4 (enterprise storage via S3/RDMA, upcoming).
- **Benchmark:** Llama 3 405B, 128K context, H100 GPUs, 2×100 Gbit Ethernet. Fetching KV cache from VAST vs. recomputing prefill: **20× improvement in TTFT**. 90% GPU time savings.
- **Economics:** 100K GPU cluster over 3 years: ~$66M savings from cache offload vs. recompute.
- **Workload profile:** KV cache workloads are heavily read-based with large blocks (megabytes range). Optimizing block manager turns slow GPU-bound IO into high-throughput network-bound transfers. Storage scales with network.
- **Data reduction:** 1.4:1 compression ratio across document, code, and chatbot KV cache datasets (1.2TB test). Enables extended sessions, more users, higher cache hit rates.
- **G3.5 (upcoming):** Deploy VAST cnode software onto BlueField DPUs. Local SSDs on each DGX/HDX server become sharable global cache at pod level. Extends node-based cache to global cache.
- **Enterprise requirements:** KV cache contains sensitive user data. Requires encryption (EU AI Act compliance), multi-tenancy isolation, SLA-driven retention policies. Enterprise storage provides these by default.

---

## 4. Serving Architecture & Ray Serve

### HAProxy + Split Control/Data Plane (Google / Anyscale)
[r9rV_c5_5uo](https://www.youtube.com/watch?v=r9rV_c5_5uo)

- **Legacy bottleneck:** Ray Serve proxy = single Python process (uvicorn). Every response token forwarded through intermediate ingress deployment. Sublinear replica scaling — throughput plateaus.
- **HAProxy replacement:** Production load balancer (Reddit, Stack Overflow, Twitter). Bypasses GIL; true multi-threading. Bundled with `rayserve[extras]` since Ray 2.57. Enable via `RAY_SERVE_ENABLE_HAPROXY` env var (Ray 2.55+).
- **Split control/data plane:** Ingress deployment replaced with queryable "ingress request router" (control plane). HAProxy makes one-time routing query per request, then streams response tokens directly from model replica to client. Supports prefix-cache-aware routing, session-aware routing, KV-cache-aware routing — just moved from hot path to control plane.
- **Results:** 9× streaming throughput. 4.4× throughput for prefill-heavy. **24× throughput for decode-heavy.** 
- **GKE validation:** Gemma 4 E2B on 8 B200 GPUs. New Ray Serve vs. old: 5× output throughput, 8× lower latency. New Ray Serve closely tracks plain vLLM without Ray overhead.
- **Inference Gateway (Kubernetes):** Multi-cluster, multi-region routing. Gateway API + HTTPRoute objects. Body-based routing extracts model ID. Model Armor for unsafe request filtering. Apigee for rate limiting/auth.
- **CubeRay features:** Zero-downtime incremental upgrades (default in CubeRay 1.7). TPU first-class support (v7x, 8i). TPU webhook handles rack alignment scheduling.

### Ray Serve Controller Scaling to 4K+ Replicas (Anyscale)
[Y1izakNit-g](https://www.youtube.com/watch?v=Y1izakNit-g)

- **Problem:** Beyond 1,000 replicas, cluster performance degrades. Autoscaling lags → requests queue → latencies spike → dashboard stops responding.
- **Controller architecture:** Single Python process, single asyncio event loop. Reconciliation loop: node update → deployment state → application state (autoscaler) → proxy state → 100ms async sleep. RPCs only execute during sleep. Autoscaling decision at step N applied at step N+1.
- **Benchmark app:** Two deployments (metric generator + hello world). Each replica emits autoscaling metrics + handles emit per-replica metrics. Maximally saturates controller event loop.
- **Optimizations:**
  - **Pydantic v1→v2:** Rust-based validation. Free performance improvement. Avoid serialize→mutate→recreate pattern; use `model_copy` instead. Single change: 83ms → 11ms (8×).
  - **Cython autoscaler:** K-way merge + backward average across time series from all replicas/handles. Pure Python → Cython: 24ms → 2ms (13×).
  - **Metrics injection (zlib compression + throttling):** Handle metric objects up to 70–80 KB. Replaced cloudpickle with zlib L3 compression. Throttle RPCs at source (stop sending if previous in-flight). Result: metrics delay bounded <2s vs. 80s snowball. CPU flame graph dramatically cleaner.
  - **Sliding window health checks:** Instead of looping all replicas every tick, slide over a subset (factor 0.5 default). Always include replicas with ongoing health checks or marked for migration.
- **Results:** 1K → 4K replicas. Control loop 32× faster. Decisions/sec 9× faster. RPC freshness 400× better.
- **Future (4K→8K):** Push-based health checks (replicas report to controller instead of controller polling). Node-level RPC aggregation (dedicated per-node process aggregates data before sending to controller).

---

## 5. Agentic & Production Serving

### Serving LLMs for Agents (JPMorgan Chase)
[B5doxR8q_rU](https://www.youtube.com/watch?v=B5doxR8q_rU)

- **Architecture:** vLLM + Ray on EKS, 3 regions, multiple AZs. CubeRay orchestrates. Separate Ray cluster per use case (even same model with different SLAs). Route53 latency-based routing → ALB → Nginx ingress (path-based) → HAProxy → model replica.
- **Self-hosting advantage:** GPT-20B self-hosted: 6–10× more efficient (cost + latency) vs. managed cloud endpoints.
- **Optimization journey (GPT-OSS 20B, RTX Pro 6000, 20K input / 300 output tokens):**
  1. Baseline Ray Serve LLM: 2,400ms
  2. Decouple vLLM from Ray distributed backend + multiprocessing + async scheduling: 1,500ms
  3. Suffix-based speculative decoding: 930ms
  4. Reasoning effort = low (for classification/tool-call tasks): 450ms
  5. HAProxy ingress: 435ms
  6. Workload-specific vLLM tuning (batch size, context length, CUDA graph, skip FP8 quant for sliding window layers): 290ms
  7. Rust-based fast tokenizer: 275ms
  - **Total: 2,400ms → 275ms (8.7× improvement)**
- **Shared suffix tree:** Replicas update common suffix tree in dedicated Ray actor. 35% higher acceptance rate. Eliminates cold-start penalty on autoscale.
- **Tokenization insight:** Default tokenizer is CPU bottleneck for large agentic prompts (conversation history + tool definitions). Rust-based fast tokenizer: modest gains on small prompts, significant on large prompts.
- **GCS fault tolerance:** External Redis backup for Ray head pod. Without: head pod failure → workers restart → cold reload model weights → minutes of downtime. With: head pod restarts, workers reconnect, zero customer impact.
- **Edge cases found:** Redis primary failover caused GCS crash (since fixed). Worker pods still sometimes restart after head node recovery (open issue). GCS + incremental upgrade interaction: new cluster restored old state from same Redis → cut traffic too early → brief downtime. Fix: dynamic Redis namespace per cluster.
- **Incremental upgrade (CubeRay):** No blue-green (GPU-constrained). New cluster starts small, gains capacity + traffic as old cluster releases it. Single-digit ms latency add from gateway class (acceptable trade-off). Rollback not yet implemented.

### Agentic AI on Intel Xeon — CPU-GPU Ratio (Intel)
[StdJgdclw6I](https://www.youtube.com/watch?v=StdJgdclw6I)

- **Core argument:** 8 of 9 agentic pipeline pressures (context retrieval, tool calls, file tracing, guardrails, sandboxing, orchestration, memory management, concurrent orchestration) are CPU-bound. Only token generation is GPU-bound.
- **Token explosion:** Single-turn ~1K tokens → multi-turn ~10K → agentic loop ~100K+ (tool calls × iterations × retrieved docs).
- **CPU-GPU ratio matters:**
  - 70B model coding task: 64s CPU + 62s GPU ≈ 1:1 ratio.
  - 8B model: GPU produces tokens faster → CPU becomes bottleneck → need more CPUs per GPU.
  - 405B+ model: GPU-heavy → 0.8:0.7 CPU:GPU ratio sufficient.
- **Head-node SLM deployment:** Running SLM on head-node CPU (otherwise idle for orchestration) increased accommodated users by 1.44× with same SLA.
- **Smart router:** Routes requests between Xeon-hosted SLMs and cloud frontier models. 27–40% cost savings at 85–95% cosine similarity accuracy vs. frontier ground truth.
- **Tool call parallelization:** GIL-bound tool calls offloaded to Ray workers. 1.6–1.7× speedup by parallelizing 8 concurrent tool calls.
- **Models under 20B:** Good fit for CPU inference. Not replacing GPU — complementing it for appropriate workloads.
- **Agentic toolkit:** Open-source, Ansible-based automation. Kubernetes orchestration. Pick-and-choose components (sandboxing, routing, memory management, inference).

### Async Inference at Netflix — Batch + NRT Unification
[ItAslhe8DEI](https://www.youtube.com/watch?v=ItAslhe8DEI)

- **Two execution modes, one pipeline:** Batch (ephemeral Ray cluster, run-to-completion) and Near-Real-Time (warm Ray actor pool, <2s scheduling overhead). Same Python code runs in both via "trace" abstraction — recorded list of replayable operations.
- **Trace mechanism:** `trace.pipeline()` replays ops against Ray Data pipeline (batch). `trace.to_live()` identifies stateful classes (with `__init__` for model loading), swaps them to warm actor pools. Stateless ops replay as-is.
- **Temporal orchestration:** Durable workflow. Batch: fans out by Parquet partition, launches parallel Ray Data jobs. NRT: per-model temporal task queue, workers pull from queue. Accumulator workflow batches individual events (by count or 30-min window) before launching batch job.
- **NRT worker architecture:** Actor pool at startup. Replica count = total GPU ÷ GPU per replica. Models loaded once per replica in `__init__`. Round-robin router actor in front. Queue + warm pool + scale-to-zero.
- **vLLM Omni for diffusion:** Omni-modal (text, image, audio, video as input/output). Same API as vLLM. Native disaggregated deployment. Netflix contributed Ray diffusion executor for multi-node: 3.2× faster (1 GPU) to 10.5× faster (8 GPU) vs. ComfyUI baseline.
- **Marco compute platform:** Originally for training. Gang scheduling, EFS/EFA, FSX, Docker image caching, priority job submission, queue leveling. GPUs fungible across training, batch, and NRT. Moving from Titus to native Kubernetes.
- **Scale-to-zero:** NRT control plane monitors queue depth, scales workers (each a separate Ray cluster) up and down including to zero. Multiple Ray clusters per model for fault tolerance.
- **Future:** Intelligent routing (cost/deadline/priority-based selection between NRT, batch, or sync inference). Per-modality optimizations. Auto-configure runtime + GPU settings.

---

## 6. Cost & Configuration Optimization

### Tailor-Made Inference (Simplismart)
[AaiDnelX_3Y](https://www.youtube.com/watch?v=AaiDnelX_3Y)

- **Core insight:** One model can produce 180–780 tokens/s depending on inference stack configuration. The configuration space is enormous (GPU choice, framework, kernels, quantization, parallelism, etc.).
- **Modular architecture:** Break inference stack into atomic swappable components. Mix vLLM pieces + SGLang pieces + custom kernels via YAML configuration.
- **Experimentation and Benchmarking System (EBS):** Agent generates hypotheses, runs benchmarks across permutations, evaluates results. Builds a ledger of all configurations mapped to price/performance. Given SLAs → linear programming search over EBS to find closest configuration.
- **Shadow load testing:** Mirror production traffic to candidate configuration. Benchmarks ≠ production. Example: higher concurrency than expected → KV cache plan insufficient → different optimal config. Three configs: planned → live → post-shadow-feedback.
- **Model-specific issues that aren't model issues:** Gemma 4 thought leakage was actually vLLM parser bug (chat template discrepancy), not model quality. Rewriting parser fixed it. Maintain per-model issue repos.
- **Compute strategy:** Reserved vs. on-demand. Elbow points where shared endpoints lose efficiency vs. dedicated. Simulator projects optimal GPU split between reserved and on-demand capacity.

### Vertical Mobility — MVP to Trillion Params (CoreWeave)
[uh4xtpos4mk](https://www.youtube.com/watch?v=uh4xtpos4mk)

- **Workload profiles:**
  - Agentic: latency-sensitive, high KV reuse (95%+), bursty, CPU-heavy tool calls
  - Chat: multi-turn, longer delays between turns (70–75% cache reuse), bursty
  - Batch: high SLAs (24–72h), high utilization, failure-tolerant
  - Real-time voice/image: ultra-low latency, depends on gateway/client proximity
- **Product tiers:** Serverless (pre-deployed, pay-per-token, noisy neighbor), Dedicated (guaranteed GPUs, customer manages deployments), Inference on CKS (bare Kubernetes, customer owns everything).
- **Platform architecture:** Gateway → control plane (auth, rate limits, billing) → router (cache-aware) → prefill/decode (same or disaggregated) → engines (vLLM, SGLang, TensorRT-LLM).
- **Cache-aware routing:** Critical lever. Agentic: 95%+ cache reuse. Chat: 70–75%. Use LMCache or MoonCake for offloading to storage when cache would be evicted between long turn delays.
- **Five performance levers:** (1) Cache-aware routing (2) Prefill-decode disaggregation (3) Quantization (4) Speculative decoding with customer-specific drafter training (5) Parallelism tuning (TP/PP/EP).
- **Leaderboard positions:** #1 on Artificial Analysis and Open Router for Kimi K3, Kimi K2.7, MiniMax M3, GLM 5.2 at various points.

### Ray Serve LLM on GKE — 24× Throughput (Google / Anyscale)
[r9rV_c5_5uo](https://www.youtube.com/watch?v=r9rV_c5_5uo)

- **Benchmark setup:** Gemma 4 E2B on 8 B200 GPUs. Round-robin routing. Same hardware + container image. Compared old Ray Serve, new Ray Serve, and plain vLLM.
- **Old Ray Serve:** Throughput peaks early, tapers off. Latency explodes with users.
- **New Ray Serve:** 5× output throughput, 8× lower latency vs. old. Closely matches plain vLLM — Ray overhead effectively eliminated.
- **Ray Serve LLM config ergonomics:** Model ID, model source, deployment info (replicas, autoscaling, custom request router), engine kwargs dict forwarded directly to vLLM/SGLang.
- **CubeRay on GKE:** Ray service = declarative YAML. Zero-downtime incremental upgrades (CubeRay 1.7). Model weights in cloud storage + container image streaming for faster cold starts. Mix GPUs and TPUs in same cluster.
- **Inference Gateway multi-region:** Fleet-registered GKE clusters. Single endpoint backed by multiple Ray services across regions. HTTPRoute for traffic splitting. Body-based routing + Model Armor + Apigee rate limiting.
