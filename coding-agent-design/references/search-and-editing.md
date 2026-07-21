# Search Strategies and Editing Schemes for Coding Agents

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Search Strategy Comparison (§5.1.9)

Four strategies, each with a distinct strength. Use them in combination, not
in isolation.

### Regex Content Matching (grep / ripgrep)

Exact keyword search across file contents. Fast, no infrastructure, no
semantic understanding.

**Use for**: known identifiers, error messages, import statements, any search
where you know the exact string.

**Limitation**: can't find a function by what it does, only by what it's
named.

### Filename Pattern Matching (glob)

Structure exploration without reading file content. Finds files by name
pattern.

**Use for**: finding configuration files, test files, modules by name,
understanding project layout before diving into content.

**Limitation**: tells you nothing about what's inside the files.

### Semantic Code Search

Structure-aware chunking combined with hybrid retrieval (keyword + embedding).
Finds code by meaning, not exact text.

**Industry debate**: Claude Code deliberately avoids embedding indices — no
stale index, no infrastructure, no data egress. Cursor builds them for
cross-file semantic recall. The trade-off is freshness vs recall: a live
grep is always current; an embedding index can lag behind recent edits.

**Use for**: finding code that does something when you don't know what it's
called; cross-file concept search.

**Limitation**: requires infrastructure; index can go stale.

### Symbol-Level Lookup (LSP)

AST-level definition and reference disambiguation. Understands the language
structure, not just text patterns.

**Use for**: refactoring (find all callers before renaming), tracing
interfaces, navigating inheritance hierarchies.

**Limitation**: requires a running language server; adds latency and
infrastructure.

### Strategy Pattern: Coarse to Fine

"From coarse to fine, from semantics to syntax":

1. Glob to find the relevant modules (structure)
2. Semantic search to identify the right file (meaning)
3. Grep to locate the specific lines (exact text)
4. LSP to trace call chains and references (structure-aware)

Start broad, narrow down. Don't reach for LSP when grep suffices; don't
reach for grep when glob is enough.

---

## File Editing Scheme Comparison (§5.1.10)

| Scheme | Mechanism | Pros | Cons | Best for |
|---|---|---|---|---|
| **Diff + Apply Model** | Main model outputs description; fast-apply model merges | High throughput | Requires dedicated model, training-intensive | High-volume IDE copilots |
| **Old String → New String** | Find-and-replace exact text | Simple, predictable, transparent | Fails on repeated patterns | Default starting point |
| **Line Number Targeting** | Edit specific line ranges | Precise for known locations | Error-prone in long files (off-by-one) | IDE-integrated agents |
| **Vim-like Commands** | Sequence of edit operations | Efficient for restructuring | Error-prone for weak models | Expert-model configurations |
| **String Start + End** | Match beginning and end of region to replace | Reliable for large deletions | Slightly more complex than old→new | Economical compromise |

### Practical Guidance

**Start with "old string → new string"** — safest, most transparent, easiest
to debug. The model sees exactly what it's replacing.

**Upgrade to "string start + end"** for large edits where the middle content
varies. Match the region boundaries, replace everything between them.

**Line-number approach** only with deep IDE integration that maintains
accurate line mappings. Off-by-one errors in long files are common without
live mapping support.

**Diff + apply model** is the right choice at scale (IDE copilot with
thousands of daily edits) but requires a dedicated fast-apply model and
training investment.

**Vim-like commands** suit expert-model configurations where the model can
reliably sequence operations. Avoid with weaker models — error accumulation
across a sequence of commands is hard to recover from.

---

## Implementation Tips (§5.1.8)

Practical engineering choices that improve coding agent reliability and
throughput.

### Parallel Tool Calls + Streaming Execution

Start executing the first tool call as soon as its parameters are complete.
Overlap execution with generation of subsequent calls. Don't wait for the
full response before starting work — streaming enables pipelining.

### Fine-Grained Context Management

- Support reading specific line ranges, not just whole files
- Attach line numbers to returned content so the model can reference them
  precisely
- Truncate long output with head + tail retention (preserve the beginning
  and end; summarize the middle)

Long file reads without line numbers force the model to guess at locations.
Line numbers in tool returns enable precise Edit File calls.

### Dynamic Environment Injection

Inject working directory, Git branch, recent commits, and unstaged changes as
an "Agent status bar" — updated dynamically, not baked into the static system
prompt. The model's view of the environment stays current without prompt
bloat.

### Persistent Terminal Session

Maintain a shared terminal session across commands. Environment variables and
working directory persist between calls. Without this, every `cd` is lost and
every `export` evaporates — the agent must re-establish context on every
command.

### Instant Syntax Feedback

Auto-run the linter after every file write. Present errors in the tool return
value, not as a separate observation step. The model gets feedback in the
same turn it made the change — tightening the correction loop.
