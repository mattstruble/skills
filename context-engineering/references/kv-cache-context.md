# KV-Cache-Friendly Context Layout

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Chat Template and Token Conversion

API messages (system, user, assistant, tool) are not fed directly to the
model. They are first serialized through a chat template — a
model-specific format that converts the structured message list into a
flat token sequence. The template inserts role markers, turn delimiters,
and special tokens that the model was trained to recognize.

The practical consequence: the token boundary between the system prompt
and the first user message is determined by the template, not by the
application. Two messages that appear adjacent in the API call may produce
a token sequence with a role marker between them that affects how the
model attends to each.

**Why this matters for cache layout.** The cache operates on the token
sequence, not on the message list. A change to any message changes the
token sequence from that message's position forward. Understanding where
the template places boundaries tells you exactly where cache invalidation
will occur.

---

## KV-Cache Principles

The key-value cache stores the attention computations for a prefix of the
token sequence. When the same prefix appears in a subsequent request, the
model reuses the cached computations rather than recomputing them.

**Prefix matching.** The cache is prefix-matched: the stored prefix must
exactly match the beginning of the new request's token sequence. A single
token difference anywhere in the prefix invalidates the cache from that
point forward.

**What invalidates.** Any change to the token sequence before the current
turn invalidates the cache from the point of change. This includes:
changing the system prompt text, reordering tool definitions, inserting a
new message before the current turn, or modifying any prior message.

**The cost of invalidation.** When the cache is invalidated, the model
recomputes attention for all tokens from the invalidation point to the
end of the context. For a long system prompt with many tool definitions,
this recomputation is the dominant cost of each inference call. Cache hits
eliminate this cost entirely.

**Granularity.** Cache granularity varies by serving infrastructure, but
the principle is consistent: longer stable prefixes produce more cache
reuse. A system prompt of 4,000 tokens that never changes is 4,000 tokens
of computation saved on every turn after the first.

---

## Prompt-Cache vs KV-Cache

These are two distinct caching mechanisms that operate at different levels:

**KV-cache (model-side).** Stores the attention key-value pairs computed
during a forward pass. Lives in GPU memory. Scoped to a single request or
a short session. Reused when the same prefix appears in a subsequent
request within the same serving instance.

**Prompt-cache (serving-side).** Some serving infrastructures maintain a
longer-lived cache of prefix computations across sessions and users.
When a request arrives with a prefix that matches a cached entry, the
serving layer injects the cached KV pairs rather than running the forward
pass. This extends the benefit of prefix stability across sessions and
users who share the same system prompt.

**The design implication is the same for both.** Stable prefix → more
cache reuse → lower cost and latency. The difference is scope: KV-cache
benefits within a session; prompt-cache benefits across sessions. A
well-designed prefix layout captures both.

---

## Stable/Append-Only Prefix Design

The system prompt and tool definitions form the prefix. The discipline:

**Never modify the prefix between turns.** The prefix is written once
when the session begins and never changed. New information is appended
after the prefix, not inserted into it.

**Tool definition ordering is part of the prefix.** If tool definitions
are dynamically assembled (selecting from a pool based on the task), the
order must be deterministic and stable across turns. Reordering tools
between turns changes the token sequence and busts the cache.

**Append-only trajectory.** Each turn appends new messages to the end of
the context. Prior messages are never modified. This is the natural
structure of a conversation, but it must be enforced explicitly in systems
that might be tempted to "clean up" or reorder prior messages.

---

## Volatile-Data-Last

Any field that changes between turns must be placed at the end of the
context — after the static prefix and after the stable trajectory. The
rule is absolute: a single volatile field anywhere in the prefix
invalidates the entire prefix cache.

**Common volatile fields:**

- Current timestamp or date
- Session-specific counters (turn number, tool calls remaining)
- Dynamic tool lists (tools enabled for this specific task)
- Per-request metadata (user tier, feature flags)

**Placement pattern.** Volatile fields belong in a trailing user message
or a dedicated context block appended at the end of each turn. They must
never appear in the system prompt.

**The timestamp trap.** Embedding a timestamp in the system prompt is the
most common cache-busting mistake. It appears harmless — one small field —
but it changes on every turn and invalidates the entire prefix. The fix
is always the same: move it to the end.

---

## Editable/Composable Cache Patterns

Some information needs to be updated without busting the entire prefix.
The pattern: structure the context so that updateable information lives
in a dedicated block at the end of the stable prefix, and new versions
of that block are appended rather than replacing the old version.

**Composable notes.** Instead of a single "current state" field that
changes each turn, maintain an append-only log of state updates. The
model reads the most recent entry. The prefix never changes; new entries
are appended to the trajectory.

**Editable blocks via sub-agents.** For information that must be
authoritative (not just the most recent entry in a log), delegate
retrieval to a sub-agent that returns a fresh snapshot. The main context
receives the snapshot as a tool result appended to the trajectory — the
prefix remains unchanged.

---

## Cache-Hit Maximization Under Changing Tool Sets

Agents that select tools dynamically — enabling different tools for
different task types — face a structural challenge: tool definitions are
part of the prefix, but the tool set changes per task.

**Strategies:**

**Full tool set always.** Include all tools in every request. The prefix
is always the same; the model ignores tools it doesn't need. Cost: larger
prefix, more tokens per call. Benefit: perfect cache reuse.

**Stable ordering with sparse activation.** Include all tools but use
the system prompt to specify which tools are active for the current task.
The tool definitions are static (cache-friendly); the activation
instruction is appended to the trajectory (volatile-safe).

**Grouped prefixes.** If the tool set falls into a small number of
distinct configurations (e.g., "search tools," "write tools," "admin
tools"), maintain a separate cached prefix for each configuration. Route
requests to the appropriate prefix. This trades prefix variety for cache
reuse within each group.

**Avoid per-request tool assembly.** Assembling a custom tool list for
each request produces a unique prefix for each request — zero cache reuse.
This is the worst-case pattern and should be avoided unless the task
diversity genuinely requires it.
