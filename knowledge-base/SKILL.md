---
name: knowledge-base
description: "You MUST use this skill proactively to maintain cross-session memory. Load context when resuming prior work, when the user references past sessions, or at the start of planning/strategy conversations. Propose writes whenever durable new information surfaces — decisions, constraints, preferences, new entities, investigation findings, or anything a future session would benefit from knowing, whether or not related content exists in the wiki yet. Explicit triggers: \"log this\", \"remember\", \"check the wiki\", \"load context\". NOT for self-contained coding tasks, one-off factual questions, or trivial conversation with no cross-session value."
---

# Knowledge Base

A persistent Obsidian-style knowledge graph that gives agents cross-session memory. The user is tired of re-explaining the same context every conversation. This skill solves that by maintaining a structured graph any agent can read at the start of relevant conversations and write to when durable new context appears.

## Two jobs: read and write

**Read** — when a conversation touches a topic the wiki might cover, traverse the graph from the relevant entry point and load the notes you need.

**Write** — when durable new context surfaces (a decision, a stable fact, a working preference, an investigation result), capture it as one or more atomic notes and link them into the graph.

A skill that only writes is a journal. A skill that only reads goes stale. Do both.

---

## Locating the knowledge base

The wiki path is declared in the global AGENTS.md. Look for a line matching `Knowledge base: <path>`.

If the line is absent, ask the user once: "Where's your knowledge base — what's the absolute path?"

If the path doesn't exist on disk, tell the user and stop — don't guess or create one elsewhere.

If the path exists but `INDEX.md` is absent, the wiki is uninitialized. Offer to scaffold it: "Your knowledge base directory exists but has no INDEX.md — want me to create the initial structure?" If they agree, create `INDEX.md` with the MOC-of-MOCs template from the Graph model section below.

---

## Reading

### When to read

- **At the start of any planning, brainstorming, strategy, or discussion conversation** that touches a known topic (project, person, ongoing investigation). Start at `INDEX.md`, jump to the relevant MOC, then load only the atomic notes you need.
- **Mid-conversation when you notice a context gap** — the user references something as if you should know it. Stop, traverse, then continue.
- **When the user explicitly asks** — "load context", "check the wiki", "what do we know about X".

Do NOT read for:
- Trivial conversations (a quick factual question, a one-off coding task)
- Coding subagent tasks spawned by an orchestrator
- Conversations that clearly have no cross-session context

### How to traverse

1. **Read `INDEX.md`** to see what MOCs exist.
2. **Read the relevant MOC.** It points to the atomic notes in that domain.
3. **Pick the 1-5 atomic notes most relevant** to the current conversation. Read them.
4. **Follow wikilinks selectively.** If a loaded note links to a relevant entity, read that note too. Don't follow every link — follow the ones that earn it. Never read the same file twice in one traversal — maintain a visited set.
5. **Use grep for backlinks** when needed. To find what decisions touched a topic, grep for its wikilink path. If grep returns more than 10 matches, load only the 3-5 most recently updated.
6. **Use tags to find clusters.** To find every active decision, grep for `tags:.*status/active` inside `decisions/`.
7. **Check decision status.** When loading a decision note, check its `status` field. If `status: superseded`, follow the supersession chain to the current active decision.

### Don't narrate

Don't say "let me load your context" or "I've reviewed your wiki." Absorb it and respond as if you already knew it.

---

## Writing

### When to write

**Explicit** — the user says "log this", "remember this", "add to the wiki", "wrap up", "save this", or similar. Write immediately.

**Proactive detection** — you notice a durable fact has surfaced that the wiki doesn't yet have:
- A decision with reasoning
- A stable preference or working style
- A new entity (a person, a collaborator, a tool choice)
- An ongoing investigation's conclusion or current state
- A constraint or commitment that will affect future work
- A novel discovery during active work (library quirks, environmental constraints, non-obvious behaviors, hard-won debugging findings)

When you detect one of these, **propose the write before doing it**: "Sounds like a new decision — want me to add `decisions/2026-04-12-cache-strategy.md` and link it from the Project MOC?" If they agree, write. If they decline, drop it.

A write doesn't require pre-existing wiki content on the topic. If nothing related exists yet, that's a reason to create a new note, not a reason to skip the write.

Don't propose writes for: today's mood, a passing question, a half-formed thought, speculation the user hasn't committed to, content already in conversation memory.

### How to write

1. **Identify the node type.** Person, org, decision, topic, or MOC?
2. **Check whether a node already exists.** Grep filenames and `aliases:` fields in the relevant folder. If it exists, update — don't duplicate.
3. **Check for contradictions.** If the new content contradicts an existing note, surface the conflict to the user before writing: "This conflicts with what's in `topics/X.md` — should I update the existing note or create a new decision that supersedes it?"
4. **Create the atomic file** with proper frontmatter, wikilinks, and folder placement.
5. **Update the relevant MOC** to include the new note.
6. **Bump `updated:`** on any note whose body or frontmatter you changed.

### Batching writes

If a conversation surfaces multiple durable facts, batch them into one write session at a natural break (or when the user says "wrap up"). Don't interrupt flow with five separate "want me to log this?" prompts.

When proposing a batch, present a numbered list in a single proposal:

> I'd like to log a few things from this session:
> 1. `decisions/2026-05-05-redis-for-session-cache.md` — the caching decision
> 2. `people/jordan.md` — new infra team lead
> 3. Update `topics/data-pipeline.md` — current migration state
>
> Want me to write all of these, or just some?

Write only the items the user approves.

Explicit user commands ("log this") always trigger an immediate write regardless of batching state — don't defer them.

---

## Graph model

The wiki is a graph. Each markdown file is a **node**; every `[[wikilink]]` is an **edge**.

### Node types

Every note declares its `type` in frontmatter. Five canonical types:

| Type | What it is | Folder | Examples |
|---|---|---|---|
| `person` | An individual human | `people/` | `people/jordan.md` |
| `org` | A company, team, service, or project entity | `orgs/` | `orgs/infra-team.md` |
| `decision` | A dated, reasoned decision | `decisions/` | `decisions/2026-05-05-redis-for-session-cache.md` |
| `topic` | A concept, feature, strategy, or living-fact reference | `topics/` | `topics/data-pipeline.md` |
| `moc` | Map of Content — curated entry point linking related notes | `moc/` | `moc/project-MOC.md` |

When a new note doesn't fit one of these types, prefer `topic`.

### Atomic notes

**One concept per file.** Don't bundle five decisions into one log file, don't put three people on one page. Each atomic note has a single subject and links out to related notes.

When in doubt, split.

### Wikilinks (edges)

Use **full-path wikilinks**: `[[people/jordan]]`, not `[./people/jordan.md]` and not bare `[[jordan]]`. Full paths make grep-based backlink discovery trivial.

Use the alias form when prose needs a different display: `[[people/jordan|Jordan]]`.

Every meaningful entity reference in prose should be a wikilink. The link density *is* the graph.

### Frontmatter schema

Every note begins with YAML frontmatter:

```yaml
---
type: person | org | decision | topic | moc
title: "Human-readable title"
aliases: ["Alt name", "Abbreviation"]
tags: [type/person, domain/myproject, status/active]
created: 2026-05-05
updated: 2026-05-05
related: ["[[orgs/infra-team]]", "[[people/jordan]]"]
---
```

Field rules:
- **`type`** — one of the five canonical types.
- **`title`** — display title; can differ from filename. Required.
- **`aliases`** — alternate ways the entity gets referenced. Helps resolve ambiguous mentions. Optional but encouraged.
- **`tags`** — hierarchical tags from the taxonomy below. At minimum: `type/<node-type>`.
- **`created`** — ISO date the note was first written. Never changes.
- **`updated`** — ISO date of the last meaningful edit.
- **`related`** — the 1-6 most important neighbors, as wikilinks. Curated, not exhaustive.

Decision notes additionally carry:

```yaml
decision_date: 2026-05-05
status: active | superseded | reversed
supersedes: ["[[decisions/2026-02-08-old-decision]]"]
```

When a later decision supersedes an earlier one, set `status: superseded` on the older note and add `supersedes:` to the newer note. Don't delete the old one.

### Tag taxonomy

Hierarchical, slash-separated. Pick from these branches; extend only when none fit.

- `type/*` — `type/person`, `type/org`, `type/decision`, `type/topic`, `type/moc`
- `domain/*` — `domain/myproject`, `domain/infra`, `domain/personal`. The "what part of life is this."
- `status/*` — `status/active`, `status/deferred`, `status/superseded`, `status/draft`, `status/tbd`
- `role/*` — for people: `role/lead`, `role/collaborator`, `role/contact`
- `relation/*` — for orgs: `relation/team`, `relation/service`, `relation/vendor`
- `topic/*` — open-ended: `topic/migration`, `topic/deployment`. Use sparingly; a wikilink to the relevant `topics/` note is usually better.

Tags are for **filtering across the graph**. Wikilinks are for **declaring specific relationships**. When both apply, use both.

### Maps of Content (MOCs)

MOCs are curated, lightweight routing pages. They group related notes under sections with one-line context per link. They don't contain substance — they point to it.

Every domain with more than ~3 notes gets an MOC.

```markdown
---
type: moc
title: "Project X MOC"
tags: [type/moc, domain/projectx]
created: 2026-05-05
updated: 2026-05-05
---

# Project X

Entry point for everything related to Project X.

## People
- [[people/jordan|Jordan]] — infra team lead

## Topics
- [[topics/data-pipeline]] — current migration state
- [[topics/deployment-strategy]] — CD approach

## Active decisions
- [[decisions/2026-05-05-redis-for-session-cache]]
```

### INDEX.md: the MOC of MOCs

The root `INDEX.md` lists MOCs and the user's profile note. Agents start here.

```markdown
---
type: moc
title: "Wiki Index"
tags: [type/moc]
updated: 2026-05-05
---

# Wiki Index

## You
- [[people/me|Profile]]
- [[topics/working-style]]

## Domains
- [[moc/project-MOC|Project X]] — primary project
- [[moc/people-MOC|People]] — every person in the graph
- [[moc/decisions-MOC|Decisions]] — every dated decision
```

---

## Conventions

- **Filenames:** kebab-case, descriptive. Decisions prefixed with `YYYY-MM-DD-`.
- **Wikilinks:** full path `[[folder/slug]]`, with aliases when prose needs a different display.
- **Dates:** ISO `YYYY-MM-DD`.
- **Headings:** `#` for file title (one per file), `##` for sections, `###` for subsections.
- **Frontmatter:** YAML, fenced with `---`. Required on every note.
- **Tags:** hierarchical, slash-separated. Always include `type/<node-type>`.
- **No secrets:** never write API keys, passwords, tokens, private keys, connection strings, JWTs, or any credentials. If the user asks to log something containing secrets, decline and suggest a password manager or secrets store instead.
- **No PII drift:** don't accumulate third-party personal info (contact details, addresses, etc.) unless directly relevant to the work and the user explicitly authorizes it.

---

## Examples

**Example 1 — Explicit log, new decision**

User: "Just decided we're using Redis for the session cache instead of Postgres — log this."

You: Grep `decisions/` for "redis" or "session-cache" — none. Create `decisions/2026-05-05-redis-for-session-cache.md` with frontmatter (`type: decision`, `tags: [type/decision, domain/myproject, status/active]`, `related: [...]`) and the standard body:

```markdown
# Redis for session cache

**Context:** ...
**Decided:** ...
**Why:** ...
**Open:** ...
```

Update relevant MOCs. Confirm briefly: "Logged as `decisions/2026-05-05-redis-for-session-cache.md` and linked from the Decisions MOC."

**Example 2 — Proactive detection, new person**

User: "Had a great sync with Jordan — they're taking over the infra team."

You: This introduces a new person. Propose: "Want me to add `people/jordan.md` and link them to the infra topic?"

**Example 3 — Silent read at conversation start**

User: "Help me think through the migration strategy for the data pipeline."

You: Silently read `INDEX.md` → relevant MOC → `topics/data-pipeline.md`, recent decisions. Respond directly with informed context — don't announce the read.

**Example 4 — Mid-conversation context gap**

User: "And of course the NCCL issue is blocking us again."

You: Don't know what NCCL issue they mean. Read `INDEX.md` → relevant MOC → grep for NCCL. Load the relevant topic note. Continue informed.

**Example 5 — Declining to log ephemera**

User: "I'm wiped today, brain is mush."

You: Don't propose a wiki entry. Just respond.

---

## Anti-patterns

- **Don't bulk-load.** INDEX → MOC → atomic notes. Never read everything.
- **Don't write without checking for existing nodes.** Grep first.
- **Don't bundle multiple subjects into one file.** Atomic means atomic.
- **Don't use markdown links for inter-wiki references.** `[[people/jordan|Jordan]]` builds the graph; `[Jordan](./people/jordan.md)` does not.
- **Don't skip frontmatter.** Type, tags, dates, related. Every note.
- **Don't narrate reads or writes.** Just do it.
- **Don't propose logging mid-flow on minor details.** Batch at breaks.
- **Don't restructure the wiki unprompted.** Suggest once, let user decide.
- **Don't write speculation as fact.** Wait until the user commits.
