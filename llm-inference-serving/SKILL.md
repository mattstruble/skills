---
name: "llm-inference-serving"
summary: "Production LLM inference: parallelism strategy, speculative decoding, KV cache management, serving architecture, and cost optimization"
type: "design"
description: "You MUST consult this skill when choosing parallelism strategies (TP vs PP vs EP vs DP) for model serving, deciding whether speculative decoding helps a workload, designing KV cache management (in-GPU, disaggregated, offloaded), architecting prefill-decode disaggregation, building agentic or multi-turn inference pipelines, optimizing serving cost (quantization, MoE routing, CPU offload), or scaling Ray Serve / vLLM deployments. Also trigger when evaluating hardware for inference (NVLink domains, GB300 racks, CPU-GPU ratios) or debugging serving throughput bottlenecks. NOT for model training, fine-tuning, or RLHF — only the serving and inference path."
---

# LLM Inference Serving

**The bottleneck is never just compute — it shifts between memory bandwidth, inter-GPU communication, CPU overhead, and KV cache capacity depending on model architecture, request profile, and hardware topology.**

Every serving decision is a trade-off between latency, throughput, cost, and accuracy. The right configuration depends on your workload.

---

## Parallelism Strategy — When to Use What

Two questions drive the choice: (1) does the model fit on one GPU, and (2) what is the dominant bottleneck?

| Strategy | When to use | Bottleneck it solves | Cost |
|---|---|---|---|
| **Tensor Parallel (TP)** | Lowest latency; keep within NVLink domain | Splits layers across GPUs; 2L collectives per model | Cache capacity reduced per GPU; expensive all-reduce |
| **Pipeline Parallel (PP)** | Model too large for one NVLink domain | Sequential stages across nodes; send/receive activations | Higher latency (pipeline bubbles); cross-node bandwidth |
| **Expert Parallel (EP)** | MoE models (DeepSeek, Qwen) | Routes experts to different GPUs; dispatch/combine | Communication payload up to 20MB/token for 256 experts |
| **Data Parallel (DP)** | Throughput over latency; replicas of full model | Independent replicas handle separate requests | No latency benefit; requires enough memory per replica |
| **Combined TP+EP** | Frontier MoE on NVLink racks | TP within node (fast NVLink), EP across nodes | Best latency for MoE but highest hardware cost |
| **Combined DP+EP** | Production token-as-a-service | DeepSeek reference architecture; best utilization | Higher latency than TP+EP; better economics |

**Decision rules:**
- **Single NVLink domain (8 GPUs):** TP is default. Add EP for MoE models.
- **Cross-node (>8 GPUs):** PP for dense models, EP for MoE. Avoid cross-node TP — bandwidth is ~5% of intra-node NVLink.
- **GB300 NVL72 rack:** 72 GPUs at 1,800 GB/s each via NVLink. Treat entire rack as one NVLink domain for EP. 130 TB/s total all-to-all bandwidth eliminates MoE dispatch bottleneck.
- **Non-standard architectures (parallel track transformers):** PP maps tracks to TP axis, stages to PP axis. Reuses existing NVLink communicators. Requires custom executor to avoid compiled DAG deadlocks.

**Rule of thumb:** Heavy traffic stays inside NVLink domain. Cross-domain hops carry only lightweight data (activations for PP, expert dispatch for EP). Never route bulk collectives over Ethernet/InfiniBand when NVLink is available.

---

## Speculative Decoding — Decision Tree

Speculative decoding is the single most impactful **lossless** optimization for decode-heavy workloads. It predicts K tokens with a cheap drafter; the target model verifies all K in one forward pass via rejection sampling. Output distribution is mathematically identical.

**When it helps:**
- Decode-bound workloads (output >> input tokens)
- Structured/repetitive output (JSON, code, tool calls) — high acceptance rates
- Low-throughput regime (few concurrent requests per replica)

**When it hurts or is marginal:**
- Prefill-heavy workloads (long input, short output)
- Very high concurrency (GPU already saturated; drafter adds overhead)
- Low acceptance rate on diverse/creative output

### Algorithm selection

| Algorithm | Mechanism | Tokens/step | Key property |
|---|---|---|---|
| **Eagle-3** | Hidden-state drafter, 1 layer, autoregressive | 3–5 | Tiny; runs inside CUDA graph with zero per-launch overhead |
| **D-Flash / DSpark** | Diffusion-style parallel prediction + Markov head | 8–16 | One forward pass for all draft tokens; 2–3× more tokens/step than Eagle |
| **Suffix-based** | Suffix tree from prior requests; model-free | Varies | Zero GPU memory; no training; excellent for repetitive JSON output |
| **MTP (multi-token prediction)** | Native model heads | Varies | Built into model; no separate drafter needed |

### Optimization techniques for speculative decoding

- **Slim Spec (low-rank LM head):** The LM head (embedding→vocabulary projection) can be 50–60% of drafter latency. Insert a low-rank bottleneck: at 1/8 embedding size, get 5× speedup on that layer with 0.99 acceptance length retention. ~10% real production speedup.
- **Confidence head + prefix tree trimming:** Skip verification of low-confidence draft tokens to save verifier time.
- **Shared suffix tree across replicas:** Store suffix tree in a dedicated Ray actor. Eliminates cold-start penalty when new replicas scale up. Improves acceptance rate ~35%.
- **Custom drafter training:** Train speculators on customer-specific data for higher acceptance length. Best DSpark recipe: 48 GB300 GPUs, 12 nodes, TP8 extractors with hidden-state streaming via MoonCake connector. Best acceptance length: 4.15.

---

## KV Cache Management

KV cache grows with context length × batch size. For Llama 405B at 128K context, prefill computation cost grows near-quadratically. This is the dominant memory pressure in agentic workloads.

### Memory hierarchy (Dynamo tiers)

| Tier | Location | Latency | Use case |
|---|---|---|---|
| **G1** | GPU HBM | Lowest | Active decode; hot cache |
| **G2** | System RAM on GPU server | Low | Warm cache; overflow from HBM |
| **G3** | Networked storage (NFS/RDMA) | Medium | Warm reuse across replicas; offloaded sessions |
| **G3.5** | Local SSDs via DPU (BlueField) | Medium-low | Global cache at pod level; shared across nodes |
| **G4** | Enterprise storage (S3/RDMA) | Higher | Cold cache; long-lived sessions; compliance |

### Key patterns

- **KV cache offload:** 20× improvement in time-to-first-token vs. recomputation from scratch. 90% GPU time savings. At 100K GPU cluster scale, ~$66M savings over 3 years.
- **Cache-aware routing:** Route requests to replicas that already hold relevant KV cache. Critical for agentic (95%+ cache reuse) and chat (70–75% reuse) workloads. Integrated via Dynamo KV indexer + Ray Serve.
- **FP4/FP8 KV cache quantization:** DeepSeek V4 uses CSSA/HCA compression — 90% KV savings vs. V3.2. For sliding window attention layers, skip FP8 quantization when quant/dequant overhead exceeds memory bandwidth benefit.
- **Long context control:** Cap `max_model_len` to prevent individual requests from hogging resources. A single 1M-token needle-in-haystack test can consume ~60 seconds of GPU time.
- **Data reduction:** 1.4:1 compression ratio on KV cache offloaded to enterprise storage. Translates to extended sessions, more users, higher cache hit rates.

---

## Serving Architecture Patterns

### Prefill-decode disaggregation

Prefill is compute-bound (algorithm intensity >100). Decode is memory-bandwidth-bound (algorithm intensity ~1.3). Separating them lets each pool be independently sized and optimized.

- **Same-node slicing (B200):** Split GPU resources on one node. Avoids cross-node latency for activation transfer.
- **Dedicated pools:** Separate prefill and decode pools with a router. Adds latency from the routing hop. Best when prefills are long and would stall decode.
- **Disaggregated quantization:** Use high precision (FP16) for prefill KVs (reused by every decode token). Use low precision (W4A4/W4A16) for decode. 2.3–2.5× decode speedup with no accuracy loss.

### Request routing

- **HAProxy replacement for Ray Serve proxy:** Bypasses Python GIL; true multi-threading. 9× streaming throughput gain. 24× throughput for decode-heavy workloads. Bundled with Ray ≥ 2.57.
- **Split control/data plane:** Move routing decisions to a one-time control plane query. Response tokens stream directly from replica to client, bypassing intermediate deployment. Eliminates per-token TPOT tax.
- **Inference Gateway (GKE):** Multi-cluster, multi-region routing via Kubernetes Gateway API. Body-based routing extracts model ID from OpenAI request body. Rate limiting, auth, and safety filtering via routing extensions.

### Controller scaling (Ray Serve)

- **Ceiling:** 1K → 4K replicas (4× improvement). Control loop 32× faster. RPCs 400× fresher.
- **Key optimizations:** Pydantic v1→v2 (8× for object mutations), Cython autoscaler (13×), zlib-compressed metrics (bounded <2s vs. 80s snowball), sliding-window health checks.
- **Path to 8K:** Push-based health checks, node-level RPC aggregation.

---

## Agentic Inference Considerations

Agentic workloads generate 10–15× more tokens than single-turn chat. Each iteration adds tool calls, retrieved documents, and reasoning — compounding context across turns.

**Key pressures:**
1. **Expanding context → memory pressure.** KV cache grows with every turn. Cache-aware routing and offload are mandatory, not optional.
2. **Latency multiplication.** 10–20 inference calls per prompt iteration. Single-digit ms overhead compounds to seconds. Every hop in the serving stack matters.
3. **Concurrent orchestration.** Multiple agents sharing a box. Tool calls are CPU-bound (file system, retrieval, parsing). Offloading tool calls to Ray workers for GIL-bypassed parallelism gives 1.6–1.7× speedup.
4. **CPU-GPU ratio.** For a 70B model coding task: ~50/50 CPU/GPU time split. Smaller models (8B) produce tokens faster → CPU becomes bottleneck → need more CPUs. Larger models → fewer CPUs needed. Running SLMs on head-node CPUs can increase per-box user capacity by 1.44×.

**Production patterns:**
- **Separate Ray clusters per use case** even when serving the same model. Different SLAs (TPS, P99, prompt length) require different vLLM configs.
- **Reasoning effort tuning.** Setting reasoning level to "low" for classification/tool-call tasks: 930ms → 450ms latency reduction.
- **Fast tokenization.** Replace default tokenizer with Rust-based fast tokenizer. Gains scale with prompt size — critical for agentic prompts with full conversation history + tool definitions.
- **Shared suffix tree for JSON tool responses.** Agentic output is highly structured — suffix-based speculative decoding with shared state across replicas is a strong fit.

---

## Cost Optimization Levers

| Lever | Mechanism | Typical impact |
|---|---|---|
| **Quantization (NVB4/FP4/FP8)** | Reduce memory footprint 1.8×; exploit tensor core throughput | TPOT: 7–8ms → 4ms; enables fewer GPUs per model |
| **MoE expert parallelism** | Only 9/256 experts active per token; route efficiently | GB300 NVL72 eliminates dispatch bottleneck; 10× cheaper tokens vs. Hopper |
| **Speculative decoding** | Verify K tokens in one forward pass | ~300 additional aggregate tokens/s; best at low concurrency |
| **CPU offload (SLM routing)** | Route simple queries to CPU-hosted SLMs; frontier model for reasoning only | 27–40% cost savings at 85–95% cosine similarity accuracy |
| **Disaggregated precision** | FP16 prefill + W4A4 decode | 2.3× end-to-end speedup; accuracy matches FP16 |
| **Kernel fusion** | Fuse RMSNorm + RoPE + FP8 quant into single launch | 33 → 10 kernels; 1.2× speedup; eliminates memory round-trips |
| **Programmatic dependent launch** | Overlap dependent kernel launches | Reduces kernel launch overhead in decode path |
| **Capacity reservations + incremental upgrades** | Avoid blue-green doubling in GPU-constrained environments | CubeRay incremental upgrade: move capacity + traffic simultaneously |

---

## Hardware Selection Quick Reference

| Hardware | Sweet spot | Key property |
|---|---|---|
| **B200 (single node, 8 GPU)** | TP8 serving; moderate MoE models | 288 GB HBM; 1.5× NVB4 compute vs. prior gen |
| **GB300 NVL72 (rack)** | Frontier MoE (DeepSeek V4, Qwen 3.8, Kimi K3) | 72 GPUs, 130 TB/s all-to-all NVLink; 20× agentic perf vs. Hopper |
| **Vera Rubin (pod)** | Next-gen; 7 chip types including Groq LPX for low-latency decode | 30× over Blackwell on agentic benchmarks (silicon) |
| **Intel Xeon (CPU)** | SLM inference (<20B); tool execution; agentic orchestration | Day-zero vLLM/SGLang support; 1.44× user density with head-node SLMs |
| **Google TPU v7x / 8i** | High memory bandwidth; MoE-optimized SRAM | First-class Ray support via CubeRay TPU webhook |
