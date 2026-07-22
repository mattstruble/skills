*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

# Autonomous Capability Growth

How agents expand their tool set — from discovering existing tools to creating new ones from scratch.

---

## Tool Discovery

As an agent's available tool set grows from dozens to hundreds or thousands, finding the right tool becomes its own problem. Three approaches exist on a spectrum from heavyweight to lightweight.

### Full Injection (Breaks at Scale)

The naive approach injects every tool's complete schema into the system prompt at once. This works for small tool sets but degrades fast: the context fills with tool documentation, selection accuracy drops, and every tool change invalidates the KV cache prefix.

### Retrieval-Based Pre-Filtering

Screen tool candidates by semantic similarity before injection. This reduces context overhead but has an inherent limit: it matches once, against the user's initial query. A request like "debug this file" may require a multi-step, cross-domain tool chain that can't be foreseen at query time.

### Proactive Declaration (MCP-Zero Pattern)

The agent becomes an active discoverer rather than a passive recipient. When it hits a capability gap mid-execution, it declares in natural language what it needs, and the system matches and injects the tool on the fly. No tool schemas are pre-loaded; the agent emits structured requests ("I need the ability to query stock prices") and the system routes through two levels of semantic matching — server-level, then tool-level — before injecting.

This approach reports roughly 98% token savings over full injection for large tool sets, but requires an embedding index to maintain, KV cache invalidation management, and specific API support.

### Skills as On-Demand Lookup (Lighter Weight)

The Skills mechanism inverts the tool discovery model: at startup the agent sees only a thin catalog — each skill's name and description, a few hundred tokens total. Only when the current context genuinely calls for a capability does the agent read the corresponding skill, then follow its internal references down to specific scripts or sub-documents.

This is how humans use reference material: nobody reads a handbook cover to cover; you follow the index to exactly the entry you need, when you need it. The agent needs nothing beyond general file-reading ability (grep, read) to browse the skill directory — no vector index to maintain, no special semantic-retrieval infrastructure. It is the lower-maintenance approach for tool discovery at scale.

---

## Tool Creation (Voyager Cycle)

Proactive tool discovery solves finding tools that exist. The next capability is harder: what if the tool you need doesn't exist at all?

### The Fundamental Limitation of Predefined Tool Sets

Most agent systems rest on an implicit assumption: a sufficiently complete tool set can be defined in advance. In a closed domain this may hold. For a general-purpose agent, the assumption is wishful thinking. The tools the real world demands are nearly infinite and cannot be enumerated up front. Even when the library holds something similar, its interface rarely matches the need exactly. And many useful services simply don't exist behind agent-friendly interfaces.

The predefined paradigm caps the agent's capabilities at whatever its human engineers managed to foresee and prepare.

### The Voyager Cycle: Explore → Iterate → Verify → Store → Reuse

Voyager, an open-world agent architecture from the NVIDIA team, demonstrates the complete methodology in the virtual world of Minecraft. The same cycle applies to enterprise contexts — API wrapper generation, automation scripts, MCP server creation.

**Explore**: the agent identifies a capability gap and searches for or writes code to fill it. In open-world settings, this means searching open-source repositories, reading documentation, and synthesizing a working implementation. In enterprise settings, this means identifying which internal API or library covers the need, reading its documentation, and writing a wrapper that conforms to the agent's tool interface standard.

**Iterate on failure**: when the first implementation attempt fails, Voyager's iterative prompting mechanism kicks in. The agent gathers feedback — environmental observations, error messages, self-verification results — folds them into the LLM prompt, and generates an improved implementation. This loop continues until the code is stable. This is distinct from the workflow recording pre-storage gate (see `references/experience-distillation.md`): iterative prompting fixes the code before the task is even attempted as a candidate for storage; the pre-storage gate verifies a compiled workflow actually completes the task before it enters the library.

**Verify task completion**: once the implementation runs without errors, the agent verifies that the task was actually accomplished — not just that the code executed without crashing. This is the criterion for moving to Store: did the task succeed?

**Store**: the verified tool is registered in the tool library with its schema, description, and usage examples. Tools are hierarchical and composable: a "portfolio analysis" tool can build on a "get stock price" tool, which in turn builds on a "query financial API" tool.

**Reuse**: on future similar tasks, the agent retrieves the tool from the library rather than rediscovering or recreating it. The library grows with each new capability, and new tools can build on existing ones.

### Agent Finds Tools from the Web

The first mode of tool creation: integrating existing tools from the open-source ecosystem. Facing a task that requires a capability it doesn't have, the agent:

1. Analyzes the task requirements and identifies the needed capability
2. Searches open-source repositories and documentation for matching libraries
3. Reads the library's documentation and code examples to understand the interface
4. Writes wrapper code conforming to the agent's tool interface standard (e.g., MCP protocol)
5. Tests the wrapper and registers it in the tool library

The newly created tool is available for direct reuse on future similar tasks.

**Enterprise examples**: generating an MCP wrapper for an internal REST API the agent has never seen before; creating an automation script for a new SaaS tool the company just adopted; building a data transformation tool from a library found in the company's internal package registry.

### Agent Writes Code to Generate New Tools

The second mode: writing code from scratch when no existing library covers the need. The creation process follows standard software engineering: requirements and interface design, algorithm selection and implementation, testing and validation, schema generation, and registration.

The key difference from one-off code execution: the code ends up in the tool library, not thrown away. Experience stops evaporating at session end and accumulates permanently. Code tools behave deterministically and testably — far more reliable than making the model re-derive the solution every time.

---

## Three-Layer Capability Accumulation

Self-evolution compounds across three levels:

**Tool level**: successfully created tools enter the library and become building blocks for future tools. A "get stock price" tool enables a "portfolio analysis" tool, which enables a "risk assessment" tool. Capability grows hierarchically.

**Knowledge level**: every tool created brings heuristic knowledge — which libraries suit which tasks, which APIs work without registration, which libraries have complex dependencies or fight the environment. Extracted as rules or case libraries and stored in the knowledge base, this knowledge guides future tool creation. The agent gradually learns to evaluate open-source project quality, predict integration difficulty, and select the right library on the first try.

**Strategy level**: through repeated practice, the agent improves its self-evolution strategy itself — better library selection, more concise implementation, more thorough testing. Early on it may pick the wrong library, write overwrought logic, or miss critical edge cases; fed by both failures and successes, it learns to judge more accurately. In the short run, this meta-experience accumulates in system prompts and skills; once stable, it can be baked into weights via reinforcement learning.

The first two levels are externalized learning applied directly. The strategy level shows the relay between externalized learning and post-training: iterate fast on interpretable, editable external carriers first, and only once the strategy stabilizes consider freezing it into parameters.

---

## Safety Boundaries

Self-evolution gives agents formidable room to grow — and a set of safety risks all their own.

### Supply Chain Attack

An agent that searches for and installs open-source libraries from the internet may automatically download and execute a malicious package. Mitigations:
- Run tool creation in a sandbox with no network egress beyond approved registries
- Automatically security-scan newly created tools before registration
- Maintain an allowlist of approved package sources

### Capability Drift

The strategies and tools an agent accumulates through continuous learning can slide away from the designer's original intent, especially over long unsupervised runs. Countermeasures:
- Whitelist of permitted tool types (the agent cannot create tools that access production databases, for example)
- Limits on how far the tool library may grow before human review is required
- Periodic human review of new tools, especially those that access external systems

### Composed Capability Escalation

Whitelisting individual tool types is insufficient when tools are composable. A tool that individually passes the whitelist (e.g., "read internal API") composed with another whitelisted tool (e.g., "write to S3") can produce emergent capabilities that would be blocked if requested directly. Tool composition is a privilege escalation surface.

Countermeasures:
- Review composed tools for emergent capabilities that exceed any single component's permissions — treat a tool that calls other tools as a new permission boundary, not just the sum of its parts
- Require explicit human approval for tools that invoke other tools from the library
- Log and audit tool-to-tool call chains; alert when a chain's combined access profile exceeds a defined threshold

### Tool Quality Degradation

An auto-generated tool that lacks sufficient testing can produce wrong results at the edges, and reuse propagates those errors into later tasks. A buggy tool called repeatedly does far more damage than a one-time inference mistake. Mitigation: the pre-storage verification gate (see `references/experience-distillation.md`) applied to code tools — test before registering.

### Memory and Experience Poisoning

Content the agent processes during a task — web pages, tool outputs — may carry maliciously injected instructions. If that content settles into long-term memory or skills as "experience" without review, the attack turns persistent: a contaminated entry strikes every time it is retrieved. This is stealthier than in-session prompt injection — the victim is not one response but the agent's accumulated "knowledge."

Mitigation requires structural defenses, not just runtime framing:

1. **Structured storage format**: store experience entries in a schema that separates factual content from imperative text (e.g., `{"fact": "...", "procedure": "..."}` rather than free-form prose). Entries containing imperative language patterns in the factual fields should be flagged for human review before storage. This is a structural defense — it makes injected instructions structurally anomalous rather than relying on the model to recognize them at retrieval time.

2. **Pre-write review and source tagging**: record which task and which source each experience came from; run injection detection on untrusted content before storage. Entries from untrusted sources (web pages, external tool outputs) require stricter review than entries from internal systems.

3. **Human review gate for imperative entries**: any experience entry that contains imperative language ("always do X", "never do Y", "ignore previous instructions") requires human approval before entering the library. Automated detection is a filter, not a gate — the gate is human.

4. **Channel isolation (partial mitigation only)**: inject retrieved experience into context as reference material, not commands — tell the model explicitly that experience carries no directive authority. This reduces the attack surface for unsophisticated injections but is not a structural defense: prompt injection bypasses model-level framing by design. Treat channel isolation as a defense-in-depth layer, not the primary control.

5. **Retrieval-time detection**: lightly scan retrieved entries for injection patterns; downgrade or alert on anything suspicious.

Knowledge freshness and poison defense are two sides of one coin: freshness fights natural obsolescence, poison defense fights malicious contamination. Both require that the experience library trace sources and support entry eviction.
