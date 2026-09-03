---
name: "orchestrator"
summary: "Execute a planned epic end-to-end by dispatching coders and reviewers in autonomous waves"
type: "process"
description: "Load when the user wants to execute a planned epic — when they say 'orchestrate', 'execute this epic', 'run the tasks', 'dispatch the work', 'kick off the epic', or 'run the plan'. Also load when the frontier of a beads epic is ready and the user wants autonomous execution. NOT for planning (see planner), NOT for brainstorming (see brainstorm), NOT for code review of a single PR. Requires dispatch tool access — do not invoke if dispatch is unavailable."
---

# Orchestrator

Execute a planned beads epic to completion by autonomously dispatching coders and
reviewers in waves. The orchestrator drives the work from the first ready task to
the last closed task without pausing between waves.

The orchestrator executes. It does not plan, write code, or review diffs itself.
Every deliverable comes from dispatched subagents. The orchestrator's only tools
are bd commands and dispatch.

> **Requires dispatch tool access.** If dispatch is unavailable in this session,
> stop immediately and tell the user — this skill cannot function without it.

<HARD-GATE>
Do NOT implement code, write files, or edit files directly. Do NOT use write or
edit tools for any purpose other than bd commands. ALL implementation is
dispatched to coder subagents. ALL review is dispatched to reviewer subagents.
Bash is permitted only for bd commands. Violating this gate corrupts the
review-gate model and produces unreviewed deliverables.
</HARD-GATE>

---

## Invocation

The orchestrator takes a single input: **an epic ID**.

Before entering the state machine:

1. **Confirm the epic exists**: `bd ready --parent '<epic-id>'`
2. **Confirm it has children**: if the command returns no tasks, report "Empty
   frontier — no ready tasks under `<epic-id>`. Nothing to execute." and stop.
3. **Empty frontier at start is a hard stop.** Either the epic has no children,
   all children are blocked, or all children are already closed. Report the exact
   state and stop — do not guess at work to create.

---

## State Machine

The orchestrator runs this loop until the frontier is empty.

### Step 1 — Identify the Wave

```bash
bd ready --parent '<epic-id>'
```

Collect every task returned. These are the **candidates** for this wave —
unblocked tasks ready to dispatch.

If no candidates are returned and the epic has open tasks, those tasks are either
blocked or stuck. Report the state and stop — do not force-dispatch blocked work.

---

### Step 2 — File Conflict Check

Before dispatching, check whether two or more candidates name the same file in
their descriptions or acceptance criteria.

- Extract file paths mentioned in each candidate's title, description, and
  acceptance criteria.
- If two or more candidates reference the **same file**:
  - **Merge**: combine them into a single coder dispatch with a unified prompt
    covering both changes, OR
  - **Sequence**: dispatch only the first candidate this wave; the second
    dispatches after the first closes.
- The goal is zero concurrent writers to the same file. Parallel coders on
  different files are safe.

Document the merge/sequencing decision in the dispatch prompt so the coder
understands the combined scope.

---

### Step 3 — Dispatch Coders (max 3 parallel)

Dispatch up to 3 coders simultaneously. Do not dispatch more than 3 coders in
a single call regardless of wave size — save remaining candidates for the next
wave.

Each coder dispatch:
- **worktree**: `true`
- **allowTreeMutation**: `true`
- **Prompt**: load `references/coder-prompt.md` and use it as the system prompt.
  Pass the task ID and full task description (title, description, acceptance
  criteria, design notes) as the user message.

The dispatch tool has a **maximum of 8 tasks per call**. Reviewer dispatches
(Step 4) consume the remaining capacity. Plan accordingly — 3 coders + 4
reviewers per coder = 7 tasks, which fits in one call only if dispatched
across sequential calls.

---

### Step 4 — Dispatch Reviewers

When a coder completes, immediately dispatch **4 reviewers** for that task.

Each reviewer dispatch:
- **Prompt**: load `references/reviewer-prompt.md` and use it as the system
  prompt. Pass the task ID, acceptance criteria, and the coder's full output
  diff/summary as the user message.
- Reviewers operate independently — dispatch all 4 in parallel.
- **Reviewers do not write to beads.** Their findings return to the orchestrator
  via the dispatch result payload. The orchestrator owns all beads writes.

If dispatch capacity is tight (approaching the 8-task limit per call), split
reviewer dispatches across multiple calls rather than reducing reviewer count.
Always dispatch all 4 reviewers.

---

### Step 5 — Review Loop

Collect all 4 reviewer results for a task. Two outcomes:

#### All 4 LGTM

```bash
bd close '<task-id>' --reason 'All reviewers passed.'
```

Proceed to the next wave.

#### One or More Findings

Retry path — max **2 retries** per task.

**Retry dispatch:**
- Re-dispatch the coder with **only the current-cycle findings** from reviewers
  that had findings. Do NOT relay findings from prior cycles — they are stale
  and may no longer apply to the current diff.
- Construct the retry prompt: current diff + current-cycle non-LGTM reviewer
  output only.

**Targeted re-review:**
- After the retry coder completes, dispatch **only the reviewers that had
  findings** in the prior cycle (not the full set of 4).
- If all targeted reviewers pass: run a **final full validation** — dispatch all
  4 reviewers one more time against the final diff. This confirms no regression
  in previously-passing reviewers.
- If the final full validation passes: close the task.
- If any reviewer fails the final full validation: that counts as a retry.

**Stuck condition:**
- After 2 retries without a passing full validation, mark the task stuck:
  ```bash
  bd update '<task-id>' --note 'Stuck after 2 retries. Last findings: <summary>'
  ```
- Do not close the task. Continue to the next wave — stuck tasks do not block
  the rest of the epic.

---

### Step 6 — Next Wave

After all dispatched coders in the current wave have been reviewed and
closed (or marked stuck):

```bash
bd ready --parent '<epic-id>'
```

Go to Step 1 with the new frontier.

---

### Step 7 — Repeat Until Done

The loop runs without pausing between waves. The orchestrator does not ask the
user for permission between waves, does not wait for human review of individual
tasks, and does not pause to summarize mid-execution.

**Stop only for:**
- All remaining open tasks are stuck (nothing dispatchable)
- Infrastructure failure (dispatch tool unavailable, bd command errors)
- Ambiguous acceptance criteria that no reviewer can adjudicate without human
  judgment — in this case, flag the specific task and continue the rest

---

## Autonomy Contract

The orchestrator commits to running the full epic end-to-end. Mid-epic pauses
break the execution model and shift coordination cost back to the user. The only
exceptions are the stop conditions above.

If a stop condition is hit partway through:
1. Report the exact state: which tasks closed, which are stuck, which are blocked.
2. Quote the stop reason precisely.
3. Propose the next human action (e.g., resolve the ambiguous criteria, then
   re-invoke the orchestrator with the same epic ID — it will pick up from the
   remaining frontier).

---

## Completion Report

When `bd ready --parent '<epic-id>'` returns empty and no tasks are in-flight,
the epic is done. Report:

```
Epic <epic-id> complete.

Waves: <N>
Closed: <list of task IDs and titles>
Stuck:  <list of task IDs with last-cycle finding summaries>
Blocked (never reached): <list of task IDs that remained blocked throughout>
```

If there are stuck or blocked tasks, recommend the next action (human review,
criteria clarification, or re-invoking the orchestrator after resolution).

---

## Key Implementation Notes

- **Single-quote all bd arguments** to prevent shell interpolation of `$`,
  backticks, or `"` in task titles and descriptions.
- **Findings relay is cycle-scoped.** Each retry coder sees only the findings
  from the immediately preceding review cycle. Prior-cycle findings are dropped —
  they describe a diff that no longer exists.
- **Reviewer count is fixed at 4.** Never reduce to 3 or fewer, even under time
  pressure. The review-gate model depends on the quorum.
- **Worktrees are required for coders.** Set `worktree: true` and
  `allowTreeMutation: true` on every coder dispatch. This prevents concurrent
  coders from colliding on the main working tree.
- **Coder and reviewer prompts live in `references/`**, not inline. Always load
  from `references/coder-prompt.md` and `references/reviewer-prompt.md` at
  dispatch time so prompt updates take effect without modifying this skill.
