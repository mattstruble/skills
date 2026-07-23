# mattstruble-skills

Claude/OpenCode skills with eval-driven development.

## Skills

### Process Skills

Skills that enforce a specific way of working — a multi-step procedure or discipline the model follows once the skill loads.

| Skill | Summary | With Skill | Baseline | Δ | Last Run |
|-------|---------|-----------|----------|---|----------|
| brainstorm | Interview-driven design through relentless questioning before implementation | 100% | 67% | +33% | 2026-06-30 |
| code-reviewer | Four-reviewer parallel code review pipeline with fix cycle and aggregated findings | 100% | 100% | +0% | 2026-06-30 |
| git-commit | Conventional commit authoring: grouping changes by intent and writing commit messages | — | — | — | — |
| git-pr | Pull request creation: sizing, title conventions, and description writing | — | — | — | — |
| knowledge-base | Maintaining and writing to a persistent Obsidian-style cross-session knowledge graph | 100% | 80% | +20% | 2026-07-22 |
| logging | Production logging discipline: structured logs, happy-path coverage, correlation IDs | — | — | — | — |
| pr-reviewer | Peer PR review pipeline producing tiered, courteous draft comments for GitHub | 100% | 87% | +13% | 2026-07-22 |
| prd-to-stories | Decomposing behavioral PRDs into deliverable stories with specific acceptance criteria | — | — | — | — |
| prd-writing | Co-authoring behavioral product requirements documents through structured interview | 100% | 73% | +27% | 2026-07-22 |
| skill-creator | Creating, iterating, and benchmarking skills through eval-driven refinement | 100% | 100% | +0% | 2026-07-22 |
| test-driven-development | Red-green-refactor TDD workflow: writing tests before implementation | — | — | — | — |

### Design Skills

Skills that supply frameworks and judgment for architectural or creative decisions.

| Skill | Summary | With Skill | Baseline | Δ | Last Run |
|-------|---------|-----------|----------|---|----------|
| agent-architecture | Framework for deciding when and how to build LLM-driven agent systems | — | — | — | — |
| agent-evaluation | Designing evaluation systems, rubrics, and metrics for autonomous agents | — | — | — | — |
| agent-memory | Cross-session memory design for personalized agents: storage, consolidation, retrieval | — | — | — | — |
| agent-post-training | Decision framework for when and how to fine-tune models for agent tasks | — | — | — | — |
| agent-self-evolution | Designing agents that accumulate experience and improve across sessions without retraining | 100% | 75% | +25% | 2026-07-22 |
| agent-tool-design | Designing tool interfaces that LLMs can reliably discover, select, and invoke | — | — | — | — |
| api-design | REST and gRPC API conventions: resource modeling, naming, versioning, error handling | 100% | 100% | +0% | 2026-06-30 |
| application-architecture | Layering, domain modeling, and data access patterns for application-level structure | 100% | 25% | +75% | 2026-06-30 |
| coding-agent-design | Building coding agents: toolset design, security model, workflow, and failure handling | — | — | — | — |
| concurrency-design | Choosing thread topology, concurrency units, and inter-component communication models | 93% | 67% | +27% | 2026-07-22 |
| context-engineering | Structuring LLM context windows for cache efficiency and instruction persistence | — | — | — | — |
| game-audio | Audio design principles for games: music, sound effects, and adaptive systems | 100% | 73% | +27% | 2026-07-22 |
| game-design | Frameworks for analyzing mechanics, game feel, player motivation, and systemic design | 100% | 75% | +25% | 2026-06-30 |
| game-narrative | Applied interactive storytelling: deduction systems, NPC agency, non-linear discovery | 100% | 100% | +0% | 2026-06-30 |
| game-patterns | Engine-agnostic game programming patterns: ECS, state machines, event systems, pooling | 100% | 75% | +25% | 2026-06-30 |
| game-performance | Systematic GPU/CPU/memory profiling and optimization methodology for games | 100% | 100% | +0% | 2026-06-30 |
| game-visuals | Visual design principles for legibility, color hierarchy, and art direction in games | 100% | 33% | +67% | 2026-06-30 |
| level-design | Combat arena and action game level design: spatial choice, legibility, encounter flow | 100% | 80% | +20% | 2026-07-22 |
| love2d-fennel | Fennel + Love2D interactive development: REPL workflow, hot-reloading, mode architecture | — | — | — | — |
| ml-post-training | SFT and RL post-training mechanics: data pipelines, reward design, LoRA, debugging | — | — | — | — |
| multi-agent-collaboration | Designing multi-agent topologies, context sharing, handoff protocols, and failure modes | — | — | — | — |
| nix | NixOS, Home Manager, nix-darwin, flakes, devShells, and declarative system configuration | — | — | — | — |
| nix-dendritic | Aspect-oriented flake-parts Nix configuration for multi-host, multi-platform setups | — | — | — | — |
| odin-design | Idiomatic Odin patterns, allocators, package structure, and LLM knowledge-gap corrections | — | — | — | — |
| odin-gamedev | Odin game architecture with Raylib/Sokol: entity management, hot reloading, game state | — | — | — | — |
| python-design | Python-specific design patterns, idioms, type choices, and anti-patterns | — | — | — | — |
| rag-design | Retrieval pipeline design: chunking, embeddings, hybrid retrieval, and structured indexes | — | — | — | — |
| software-design | Core software design principles: composition, minimal interfaces, and clean boundaries | 100% | 75% | +25% | 2026-06-30 |
| test-design | Test quality tradeoffs using Kent Beck's Test Desiderata: behavior over structure | 100% | 67% | +33% | 2026-06-30 |

### Reference Skills

Skills that provide domain facts and syntax the model already knows; they exist for consistent routing and conventions.

| Skill | Summary | With Skill | Baseline | Δ | Last Run |
|-------|---------|-----------|----------|---|----------|
| docker | Dockerfile authoring, multi-stage builds, image optimization, and container networking | — | — | — | — |
| game-rendering | 3D rendering pipeline math: coordinate spaces, rasterization, projection, lighting | 100% | 67% | +33% | 2026-06-30 |
| godot | Godot 4.x GDScript development: scenes, nodes, signals, AutoLoads, and patterns | 93% | 60% | +33% | 2026-07-22 |
| godot-shader | Godot 4.x GDSL shader authoring: spatial, canvas_item, and particle shaders | 100% | 100% | +0% | 2026-07-22 |
| gpu-rendering-architecture | Modern GPU programming model: bindless resources, GPU-driven rendering, synchronization | 100% | 100% | +0% | 2026-07-22 |
| grafana | Grafana dashboard authoring, template variables, IaC provisioning, and alerting | 100% | 100% | +0% | 2026-07-22 |
| helm | Helm chart installation, value overrides, upgrades, rollbacks, and chart discovery | 100% | 100% | +0% | 2026-07-22 |
| homelab-monitoring | Deploying Loki, Prometheus, Grafana, and Alertmanager on k3s or Docker Compose | 100% | 93% | +7% | 2026-07-22 |
| k3s | Installing and managing self-hosted Kubernetes clusters with k3s | — | — | — | — |
| k8s-networking | DNS, Ingress, TLS, NetworkPolicy, and VPN access for self-hosted Kubernetes | — | — | — | — |
| k8s-operations | Day-2 Kubernetes operations: probes, rollouts, hardening, and deployment automation | 100% | 100% | +0% | 2026-07-22 |
| k8s-storage | Kubernetes ConfigMaps, Secrets, PersistentVolumes, and backup strategies | 100% | 100% | +0% | 2026-07-22 |
| k8s-workloads | Kubernetes workload resources: Deployments, StatefulSets, DaemonSets, Jobs, Services | 100% | 100% | +0% | 2026-07-22 |
| logql | LogQL query syntax for Grafana Loki: filtering, parsing, and log-based metrics | 100% | 100% | +0% | 2026-07-22 |
| love2d | Love2D 11.x Lua development: callbacks, input, shaders, and game loop patterns | — | — | — | — |
| nix-packaging | Writing Nix derivations with stdenv and language-specific builders from scratch | 100% | 100% | +0% | 2026-07-22 |
| promql | PromQL query syntax for Prometheus: rates, histograms, alerting, and capacity planning | 100% | 100% | +0% | 2026-07-22 |

[Detailed per-eval results →](evals/README.md)

## Structure

```
<skill>/SKILL.md       — skill definition + references
evals/<skill>/         — eval definitions + benchmarks
scripts/               — tooling (generate_readme.py)
```
