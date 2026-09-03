---
name: "planner"
summary: "Decompose a well-understood effort into a typed, critic-reviewed task graph ready for execution"
type: "process"
description: "Load when a request is about planning, decomposing, or scoping work into tickets — when the user says 'plan this', 'break this down', 'create tickets for', 'scope this out', or 'what are the tasks'. Also load when coming out of a brainstorm session and the next step is task creation. NOT for brainstorming (see brainstorm), NOT for debugging, NOT for code review, NOT for implementation. The output of this skill is a task graph, not built software."
---

# Planner

Turn a scoped piece of work into a typed, dependency-wired task graph — reviewed by a critic, presented to the user, and waiting for approval before anything gets built.

The planner produces plans. It does not produce deliverables. The discipline here is the same as brainstorm's: understanding precedes action, and the user approves the graph before execution begins.

<HARD-GATE>
Do NOT create tickets speculatively, implement anything, write code, or scaffold
any project during the planning session. The task graph is the output. Stop when
the graph is presented and wait for user approval before any ticket is claimed or
any work begins. This applies to both classification paths.
</HARD-GATE>

## Initial Context Scan

Before classifying, load context. This is non-negotiable — planning from memory
produces plans that don't fit the domain.

1. **Read `~/llm-wiki/INDEX.md`** to see what domains exist.
2. **Read the MOC** most relevant to the work being planned.
3. **Load 1–5 atomic notes** that bear on this effort — constraints, past decisions, active preferences.
4. **Check `plans/`** in the wiki for any active map or prior planning artifact on this topic.

Don't narrate the read. Absorb and proceed.

---

## Classify the Effort

Before asking questions or creating anything, classify the scope of work. Announce
the classification so the user can override it.

### Simple

The work is **visible end-to-end from here**. You can name every ticket without
investigation. The full effort fits comfortably in a handful of beads tasks with
clear dependencies. No sessions are needed to figure out what comes next.

Signal: the user describes work you can mentally decompose in one pass. The path
from start to done is obvious.

**→ Follow the Simple Path.**

### Foggy

The work spans **multiple sessions** and the destination is unclear from here.
Resolving early tickets will change the shape of later ones. You cannot name all
the tickets now because the route is genuinely obscured.

Signal: the user describes something big, novel, or uncertain — greenfield, large
refactor, exploratory work, unclear success criteria. Phrases like "figure out
how to", "research whether", "design the approach for".

**→ The Foggy Path protocol is defined in a separate extension of this skill.**
**See task mattstruble-skills-we2 for the full map-and-frontier protocol.**
**For now: tell the user this effort is foggy, confirm the classification, and**
**stop. Do not create tickets. The foggy protocol must be loaded before proceeding.**

---

## Simple Path

### 1. Invoke Brainstorm to Confirm Scope

Don't trust the initial description. Invoke the brainstorm skill to confirm what
the work actually is, surface assumptions, and make sure nothing is missing before
the graph gets wired.

Brainstorm grills until the scope is solid. The planning session begins when
brainstorm signals done — not before.

**Re-classify after brainstorm.** If brainstorm reveals that scope is larger than expected, success criteria are still unclear, or you cannot yet name all the tickets, re-classify this effort as Foggy and stop per the Foggy protocol — do not proceed to ticket creation.

### 2. Create Typed Tickets

With scope confirmed, create beads tasks. Every ticket carries a **type tag** in
its title. The tag is the first word of the title, in brackets:

| Tag | When to use |
|---|---|
| `[research]` | Unknown facts must be established before the work can proceed. AFK-capable. |
| `[brainstorming]` | A design decision requires a live grilling session. HITL. |
| `[prototype]` | A question is best answered by building something cheap and throwaway. HITL. |
| `[human-task]` | Only a human can do this: provisioning, credentials, external approvals. HITL. |
| *(no tag)* | Standard implementation ticket. Scope is clear and the agent can execute. |

Use `bd create "<title>" --parent <parent-id>` for each ticket. Size tickets to
one focused session — if a ticket would require more than one agent context window,
split it.

### 3. Wire Dependencies

After all tickets exist (they need IDs to reference each other), make a second
pass to add blocking edges:

```
bd dep add <blocked-id> --needs <blocker-id>
```

The dependency graph determines the **frontier** — the set of tickets that are
unblocked and ready to claim. A correct graph means agents can always see what's
takeable without reading the whole plan.

### 4. Critic Loop

Spawn a `plan-critic` subagent to stress-test the task graph before presenting it
to the user. The critic's job:

- Are any tickets missing that the plan silently assumes?
- Are any tickets scoped too large to execute in one session?
- Are dependencies complete? Any ticket that assumes a prior result without a
  declared blocker?
- Do the ticket types match the actual nature of the work?
- Is there scope that should be cut (YAGNI)?

Incorporate the critic's findings. Re-run only if the graph changed substantially.
One critic pass is the default; the goal is a tight graph, not a perfect one.

### 5. Present and Wait for Approval

Present the task graph to the user:
- List tickets in dependency order (blockers first)
- Show the type tag and a one-line description for each
- Highlight the frontier — tickets ready to claim right now
- Note any assumptions or open questions that remain

Then stop. The user approves the graph before any ticket is claimed or any work
begins. If they request changes, revise and re-present. Don't start executing
until you hear an explicit yes.

---

## Beads Conventions

- `bd create "<[type] title>" --parent <id>` — create a ticket under the parent
- `bd dep add <id> --needs <blocker-id>` — wire a blocking edge
- `bd ready <id>` — mark the frontier tickets as ready after approval
- `bd update <id> --claim` — claim before any work starts (done by the executor, not the planner)

---

## Ticket Sizing

A ticket is the right size when:
- One agent can hold the full context of the work in a single session
- It has a clear, testable done condition
- It does one thing

Split when a ticket spans multiple independent concerns, requires context that
won't fit in one window, or describes "build the whole X" rather than one
specific aspect of X.

Merge when two tickets have no independent value — if ticket B is meaningless
without ticket A already done and incorporated, they may be one ticket.
