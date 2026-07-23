---
name: agent-tool-design
summary: Designing tool interfaces that LLMs can reliably discover, select, and invoke
type: design
description: You MUST consult this skill when designing or reviewing tool interfaces that LLMs consume — function-calling schemas, MCP tool definitions, tool descriptions, parameter design, granularity decisions, or whether a capability needs a dedicated tool vs a general executor. Also trigger when an agent picks the wrong tool, calls a tool with wrong parameters, or a tool works for humans but the agent can't use it reliably. When wrapping a REST API as an MCP tool, both this skill and api-design should fire: api-design shapes the HTTP surface, this skill shapes how the LLM perceives it. NOT for HTTP API surface design for human callers (see api-design). NOT for agent runtime loop or orchestration (see agent-architecture).
---

# Agent Tool Design

**The interface the LLM sees is not the same as the interface a human sees.**

Tool interfaces for LLMs (the Agent-Computer Interface, ACI) serve the
model's reasoning process, not a human's memory. The north star is
poka-yoke: design out misuse so the error cannot happen.

---

## Framing — The ACI Model

HCI (Human-Computer Interface) is designed for human memory, attention, and
error recovery. ACI is designed for a model that reads everything in one
pass, mid-task, with limited attention to spare.

Three consequences:

- **Descriptions are instructions.** The model reads a tool description the
  same way it reads a prompt — as text it must reason from. A vague
  description is a vague instruction.
- **The model cannot ask for clarification.** A human who misreads a UI can
  hover, click around, or ask. The model must act on what the description
  says. Ambiguity becomes errors.
- **Misuse must be designed out, not documented away.** Poka-yoke: if a
  parameter can be passed in the wrong format, it will be. The tool must
  reject it cleanly, not silently mangle it.

These three properties drive every decision in the sections below.

---

## Tool Taxonomy

Five categories, each with distinct design constraints:

| Category | What it does | Key concern |
|---|---|---|
| **Perception** | Read-only information acquisition | Bounded output, explicit truncation |
| **Execution** | Changes the external world | Security layers, idempotency, sandboxing |
| **Collaboration** | Drives sub-agents or humans | Context passing, HITL handoff |
| **Event-triggered** | Agent registers; external system triggers | Trigger clarity, payload completeness |
| **User communication** | Conveys info to user outside the session | Channel selection, async messaging |

-> Read `references/tool-categories.md` for per-category design patterns.

---

## Symptom Table

| Symptom | Decision Point |
|---|---|
| Agent keeps picking the wrong tool | §4 — Description craft |
| Agent calls tool with wrong parameters | §4 — Examples / §5 — Fidelity |
| Tool count is exploding | §2 — Granularity / §1 — dedicated-vs-skill gate |
| Agent takes too many steps for one goal | §2 — Granularity (too fine) |
| Tool works for humans but agent can't use it | §3 — Generality / §4 — Description boundaries |
| Agent confused by tool results | §5 — Fidelity (silent transformation) |

---

## §1 Dedicated Tool Gate

**The question**: Should this capability be a dedicated tool, or a skill
document executed by a general executor (bash, code-interpreter)?

Three decision criteria:

| Criterion | Dedicated tool | Skill + general executor |
|---|---|---|
| **Parameter complexity** | Structured, validated, typed inputs required | Free-form or natural-language invocation is fine |
| **Frequency of change** | Stable interface; changes are rare | Evolves often; updating a doc is cheaper than redeploying a tool |
| **Model capability** | Requires special permissions, external API, or OS-level access | Model can generate the code/command itself |

**YAGNI gate.** If the model can write a Python snippet or shell command to
accomplish the task, a skill document + code-interpreter is cheaper to
maintain and more flexible than a dedicated tool. Dedicated tools are
justified when: the operation requires credentials the model shouldn't hold
directly, the interface must be stable across many agents, or the operation
is security-sensitive enough to warrant a controlled surface.

---

## §2 Granularity

**The question**: Should these capabilities be one tool or many?

**Core criterion**: functional similarity and overlap in usage scenarios.
Tools that are always called together, or that operate on the same logical
object, are candidates for merging.

**Concrete threshold**: past ~100 tools, even advanced models begin picking
the wrong one. Tool proliferation is a selection-accuracy problem, not just
a context problem.

**Merge signal** — combine when:
- Tools differ only by input format, not by what they do
- The model must always call them in sequence
- Distinguishing between them requires domain knowledge the model shouldn't need

**Split signal** — separate when:
- Tools have meaningfully different side effects or permission requirements
- Combining them would make the description too long to be useful
- One is read-only and the other writes

**Example.** `extract_pdf_text`, `extract_docx_text`, `extract_pptx_text` →
unified `read_document(path, file_type)`. The model no longer needs to know
which extractor to call; it just knows it wants document text.

---

## §3 Generality

**The question**: Given this IS a dedicated tool — should it accept
free-form inputs and leverage the model's reasoning, or enforce a structured
interface? (§1 asks whether to build a tool at all; §3 asks what kind.)

Bojie Li argues general tools are preferable unless there is a specific
reason for a dedicated tool. The LLM already reasons and generates code —
leverage that capability rather than building narrow wrappers around it.

**General is better when**: the task is expressible as code or a command,
the model's reasoning can handle variation, and no special permissions are
needed.

**Dedicated is justified when**:
- The operation is security-sensitive and must be audited at a controlled surface
- Special permissions or credentials are required (filesystem scope, API keys)
- Complex configuration must be hidden from the model
- Performance requirements demand a native implementation

**Example.** A `code_interpreter` tool beats a four-function calculator. The
model can generate arithmetic expressions, handle edge cases, and extend to
new operations — without any tool changes. A dedicated calculator tool adds
maintenance cost for no capability gain.

---

## §4 Description Craft

**The #1 lever for tool quality.** Most tool selection and parameter errors
trace to inaccurate or incomplete descriptions, not model weakness.

### "When to use" beats "what it does"

Descriptions that tell the model *when to invoke* the tool outperform
descriptions that explain *what the tool does internally*.

| | Example |
|---|---|
| **Bad** | `search`: Search for content |
| **Good** | `search`: Use when needing real-time or recent information not in training data. Returns ranked web results. |

The model reads descriptions mid-task with minimal attention. "When to use"
maps directly to the model's decision: "should I call this now?"

### Boundaries matter more than capabilities

What the tool **cannot** do, and what it does **not** accept, prevents more
errors than listing what it can do. Most failures occur because the model
doesn't know what the tool can't handle.

| | Example |
|---|---|
| **Bad** | `read_file`: Read a file from disk |
| **Good** | `read_file`: Read a local file by absolute path. Does NOT support URLs, glob patterns, or directories. Returns raw text; binary files will be garbled. |

### Parameter descriptions need concrete examples

Mid-task, the model spares minimal attention for format parsing. Concrete
examples eliminate ambiguity that type descriptions leave open.

| | Example |
|---|---|
| **Bad** | `start_time`: RFC3339 format |
| **Good** | `start_time`: RFC3339 format, e.g., `2024-03-15T14:30:00Z`. Timezone required — bare dates rejected. |

### Return value description

Describing the return structure reduces parse errors and prevents the model
from guessing at field names.

```
Returns JSON array. Each element: {title: string, url: string, snippet: string}.
Empty array when no results. Never null.
```

### Execution cost notes

Helps the model plan invocation order and avoid redundant calls.

```
Downloads the entire webpage; large sites take 5–10s. Cache is not used.
Prefer search() to find the URL before calling this.
```

### Invocation examples (1–5 per tool)

JSON Schema describes types but cannot convey invocation patterns. Bojie Li
reports examples improve tool selection accuracy from ~72% to ~90%.

```json
// Good: search for recent news
{"query": "OpenAI GPT-5 release date", "max_results": 5}

// Good: narrow to a domain
{"query": "site:arxiv.org transformer attention", "max_results": 10}

// Bad (too vague — model won't learn from this):
{"query": "something"}
```

### Debug principle

When an agent picks the wrong tool, check descriptions first. Rewrite the
"when to use" clause and add a boundary clause before concluding the model
is at fault.

---

## §5 Parameter Fidelity

**No systematic discrepancy between the world the model perceives and the
world the tool operates on.**

If the model reads a value from context and passes it to a tool, the tool
must receive exactly what the model passed. Silent transformations break the
model's ability to reason about its own actions.

### Anti-pattern 1: Silent input transformation

**Example (Cursor curly-quote bug).** The model reads a file containing
curly quotes (`"like this"`). It passes those quotes to an edit tool. The
parameter layer silently converts curly quotes to straight quotes before
executing. The match fails. The model retries with the same input, gets the
same failure, and cannot diagnose the problem — because from its perspective,
it passed exactly what it read.

**Rule**: if normalization is necessary, document it in the description AND
communicate it in the return value so the model can update its world model.

**Security note**: normalization applied before validation creates bypass
opportunities. A path sanitizer that checks for `../` after URL-decoding will
miss `..%2F`. Validate on raw input first, then normalize for execution.

### Anti-pattern 2: Silent parameter injection

**Example (IDE git flag).** An IDE adds `--ai-generated` to every `git
commit` call the agent makes, without the model's knowledge. Older git
versions fail on the unknown flag. The model retries the same command
repeatedly, unable to diagnose the failure because it never sees the injected
flag.

**Rule**: tool parameter passing must remain transparent. Any augmentation
the tool layer adds must be visible to the model — either documented in the
description or reflected in the return value.

---

## Routing Map

These are companion skills in the ai-agents family. Load the relevant one
when building that layer.

| Concern | Companion Skill | Source |
|---|---|---|
| Context depth & prompt design | context-engineering *(planned)* | Ch2 |
| Memory & knowledge persistence | agent-memory-rag *(planned)* | Ch3 |
| Orchestration & autonomy | agent-architecture | Ch1 |
| Coding agents & code generation | coding-agent-design *(planned)* | Ch5 |
| Multi-agent topology | multi-agent-collaboration *(planned)* | Ch10 |
| HTTP API surface for human callers | api-design | — |
| Autonomous tool creation / Voyager cycle | agent-self-evolution | Ch8 |

---

## NOT For

**Litmus**: Is the question about how an LLM perceives and invokes a tool?
→ here. Is it about the HTTP surface shape for human API callers? →
`api-design`. Is it about the agent runtime loop, orchestration, or
guardrails? → `agent-architecture`.

**Coexistence note**: both skills can fire together when wrapping a REST API
as an MCP tool. `api-design` shapes the HTTP surface (resource modeling,
status codes, versioning). This skill shapes how the LLM sees it (when-to-use
description, parameter examples, return value documentation, fidelity rules).
Neither replaces the other.

- Agent runtime loop, stopping conditions, guardrails → `agent-architecture`
- Application code structure → `application-architecture`
- Code-level design → `software-design`

---

## References

| Reference | When to read |
|---|---|
| `references/tool-categories.md` | Per-category design patterns: perception (truncation, output form), execution (security layers, idempotency, sandboxing), collaboration (context passing, HITL), event-triggered, user communication |
| `references/tool-ecosystem.md` | Ecosystem-scale problems: context overhead, tool discovery past ~100 tools, trust boundaries and supply-chain threats |
