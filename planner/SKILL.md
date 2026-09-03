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

**→ Follow the Foggy Path.**

---

## Foggy Path

The Foggy Path turns an uncertain, multi-session effort into a navigable map. The
map carries the destination, live decision trail, and fog — the set of decisions
you can sense but cannot yet name precisely. You work the frontier, graduate fog,
and keep the map current until the fog clears and the effort is done.

### 1. Invoke Brainstorm to Name the Destination

You cannot draw the map without a destination. Invoke the brainstorm skill to
grill until you can write two sentences answering: **what does done look like?**

Brainstorm should surface:
- The concrete end state (deployed thing, answered question, shipped feature)
- Rough scope boundaries — what the effort is *not*
- Any known hard constraints (deadlines, tech limitations, non-negotiables)
- The first decision the team must make to get moving

Brainstorm signals done when the destination is crisp enough to write. A
destination is crisp when a future agent reading it cold can orient in under
one minute. If brainstorm cannot name the destination, the effort isn't ready
to plan — stop and tell the user.

### 2. Create the Wiki Map Note

Create `plans/<effort-name>.md` in the wiki (the path declared in `AGENTS.md`
as `Knowledge base: <path>`), creating the `plans/` directory if it doesn't exist. Follow the plan note format:

```markdown
---
type: plan
title: "<Effort Name>"
tags: [type/plan, domain/<X>]
status: active
created: YYYY-MM-DD
updated: YYYY-MM-DD
related: []
destination: "One or two lines: what done looks like."
---

# <Effort Name>

## Destination
<What reaching the end of this map looks like. 1–2 lines. Orients every session.>

## Notes
<Domain context; skills every session should consult; standing constraints or
preferences for this effort. A future agent cold-reading this should understand
the landscape in one minute.>

## Decisions so far
<!-- Populated as tickets close. Format per entry:
- [Ticket title]([[beads/ticket-id]]): one-line gist of the answer -->

## Not yet specified
<!-- Fog: in-scope decisions you can't ticket yet. Write them as loosely or
fully as the view allows. These graduate into beads tickets as understanding
sharpens. Format freely — bullet or prose. -->

## Out of scope
<!-- Work consciously excluded from this effort. Never graduates. Exists to
prevent scope creep and record why something was cut. -->
```

**Plans/ directory convention:** one file per effort, kebab-case filename matching
the effort name, e.g. `plans/data-pipeline-migration.md`. After creating the map,
add it to `INDEX.md` under **Active Plans**.

### 3. Create the Epic and Frontier Tickets

Create a beads epic for the effort, then populate the frontier — the set of
tickets that can be worked right now without resolving fog first.

Frontier tickets are the work visible from here: research, design sessions, and
prototypes that will clarify the fog. Every frontier ticket carries a type tag — use the same type tags defined in the Simple Path.

Untagged (implementation) tickets belong in the fog section until enough research
has been done to define them precisely — don't create them now.

If no frontier tickets can be framed yet, create a single `[brainstorming]` ticket to sharpen the destination and treat that as the entire frontier.

Size every ticket to one focused session. If a ticket would require more than one
agent context window, split it.

### 4. Wire Blocking

After tickets exist (they need IDs), make a second pass to wire dependencies:

```
bd dep add <blocked-id> --needs <blocker-id>
```

The dependency graph determines the live frontier — tickets that are unblocked
and ready to claim. A correct graph means agents always know what's takeable
without reading the whole plan.

### 5. Critic Loop

Spawn a `plan-critic` subagent to stress-test the map and frontier before
presenting to the user. The critic's checks:

- Is the destination crisp enough to orient a future agent cold?
- Are frontier tickets sized to one session each?
- Are dependencies complete — any ticket that assumes a prior result without a
  declared blocker?
- Does the fog in *Not yet specified* cover everything known-unknown?
- Is the *Out of scope* section present and meaningful?
- Do ticket type tags match the actual nature of the work?
- Is there scope that should be cut (YAGNI)?

Incorporate the critic's findings. Re-run only if the map changed substantially. If the critic finds the destination unclear or the classification wrong, return to Step 1 before revising tickets.

### 6. Present Map for Approval

Present the map and frontier to the user:
- Quote the **Destination** — this is the anchor
- List frontier tickets in dependency order (blockers first)
- Show the type tag and one-line description for each
- Show the fog entries from *Not yet specified* — these are the open questions
- Show what's *Out of scope* so the user can correct it

Then stop. The user approves the map before any ticket is claimed or any work
begins. If they request changes, revise and re-present. Don't start executing
until you hear an explicit yes.

---

*The following applies across sessions after approval — not during the initial planning session.*

### 7. Working the Frontier (Across Sessions)

After approval, sessions proceed by working frontier tickets. After each ticket
closes, run the **fog graduation protocol**:

**Fog Graduation Protocol**

1. **Update Decisions so far** — add a line to the map:
   `- [Ticket title]([[beads/ticket-id]]): one-line gist of the answer`

2. **Check fog entries** — read each entry in *Not yet specified*. For each entry:
   - Can it now be framed as a precise, actionable ticket? If yes, **graduate**:
     create the beads ticket with the appropriate type tag, wire its dependencies,
     and remove the entry from *Not yet specified*.
   - If the entry is still too fuzzy to ticket, leave it as fog. You may sharpen
     its wording if the just-closed ticket made the question clearer.

3. **Update the map's `updated:` date** and commit.

The map body is a living document. Decisions so far grows; Not yet specified
shrinks. Out of scope never shrinks — consciously excluded work stays excluded.

### 8. Done Condition

The effort is done when:
- **Fog is empty** — *Not yet specified* has no remaining entries
- **Frontier is clear** — no open tickets remain (all closed or deferred)

When both conditions hold, set `status: complete` on the map note, remove it
from `INDEX.md`'s Active Plans section, and hand off to implementation or
whatever follow-on work the destination implies.

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
