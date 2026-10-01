---
name: "orchestrator"
summary: "Execute a planned beads epic in waves: coders and reviewers in worktrees via a workflow script, integration branch, audits, signed landing"
type: "process"
description: "Load when the user wants to execute a planned epic — when they say 'orchestrate', 'execute this epic', 'run the tasks', 'kick off the epic', or 'run the plan'. Also load when the frontier of a beads epic is ready and the user wants autonomous execution. NOT for planning (see planner), NOT for brainstorming (see brainstorm), NOT for code review of a single PR. Requires the `workflow` tool (pi-dynamic-workflows) — stop if it is unavailable."
---

# Orchestrator

Drive a beads epic from its first ready ticket to a presented, audited branch. Coders and reviewers run as
subagents inside a workflow script; you own beads, git integration, verification, and governance.

<HARD-GATE>
Never edit, write, or create files yourself — every change comes from a coder in its own worktree. Bash is for
`bd`, the git integration commands below, and verification commands from tickets. Never push. `git commit`,
`git reset`, and the final landing cherry-pick go through the user's permission prompts; do not work around them.
</HARD-GATE>

## Layout

| Thing | Where |
|---|---|
| Integration worktree | `<repo>/.pi/worktrees/epic-<epic-id>` on branch `pi/epic/<epic-id>` |
| Task worktree | `<repo>/.pi/worktrees/<task-id>` on branch `pi/wf/<task-id>`, cut from `pi/epic/<epic-id>` |
| Wave script | `references/wave.js` — pass its full text as the `workflow` tool's `script`, tasks in `args` |
| Audit script | `references/audit.js` — same, once at the end |
| Agent profiles | `coder`, `correctness-reviewer`, `failure-path-reviewer`, `readability-reviewer`, `security-reviewer`, `ticket-auditor`, `epic-auditor` |

`<repo>` is the user's checkout (`git rev-parse --show-toplevel`). Never touch its working tree or branch until landing.
Pass **absolute** paths (`<repo>/.pi/worktrees/...`) as `worktreePath` / `integrationPath`; agent `cwd` must be absolute.
Run both scripts with `background: false` so the result returns in the same turn.
Always write beads notes with `--append-notes` (`--notes` refuses to overwrite existing notes).

## 1. Start

1. `bd show <epic-id>`: the description must link a plan or design note. If none, warn the user once and continue —
   the epic audit then judges against the description and tickets only.
2. If `<repo>/.pi/worktrees/epic-<epic-id>` exists, you are resuming: read `BASE` from the epic notes, run **Resume**
   below, then continue with the waves (or straight to Audit if nothing is runnable).
3. Otherwise `bd ready --parent <epic-id>`. Empty frontier: report the state (no children, all blocked, all closed) and stop.
4. Record `BASE=$(git rev-parse HEAD)` of the user's branch, create the integration worktree
   `cd <repo> && git worktree add -b pi/epic/<epic-id> .pi/worktrees/epic-<epic-id> HEAD`, and
   `bd update <epic-id> --append-notes "orchestrator base=<BASE>"`.
5. Submodule paths, once: `git config -f <repo>/.gitmodules --get-regexp '\.path$'` (missing file = none).

## 2. Each wave

1. **Candidates:** `bd ready --parent <epic-id>` plus any tickets Resume returned to the queue, minus the set-aside list. Set aside `[human-task]`,
   `[research]`, `[brainstorming]`, `[prototype]` tickets.
2. **Submodule filter:** tickets naming paths inside a submodule (from Start step 5) are set aside, once:
   `bd update <id> --append-notes "edits submodule <path>; run in the main checkout"`.
   Set-aside tickets stay in the list for the presentation and are never re-noted.
   **No runnable candidates left → go to Audit.**
3. **File conflicts:** two candidates naming the same file go in different waves (keep the first). Tickets back for an
   integration retry run at most one per wave: they already collided once, and siblings retried together collide again.
4. **Claim** each candidate (`bd update <id> --claim`); skip any that fail.
5. **Commit message:** write one conventional-commit subject per ticket from its title and intent (git-commit skill rules:
   type(scope): imperative, lowercase, < 72 chars, no ticket IDs).
6. **Worktrees:** for each ticket,
   `cd <repo> && git worktree add -B pi/wf/<task-id> .pi/worktrees/<task-id> pi/epic/<epic-id>` (`-B` resets a branch
   left by an earlier attempt); note the integration head SHA as that task's `base`.
7. **Run the wave:** `bd update <id> --append-notes "wave started: <commitMessage>"` for each ticket, then
   `workflow({ script: <references/wave.js>, background: false, args: { tasks: [{ id, title, description, acceptance,
   commitMessage, verify, worktreePath, branch, base }] } })`. `verify` is the command from the acceptance criteria
   (tests/build), or empty. For integration retries, append the previous failure output to `description`.
   A `null` entry in `results` (that task's agent call failed outright) maps back to its task by index: treat it as stuck.
8. **Integrate** each `pass` result, one at a time, in the integration worktree:
   - `git log --oneline <base>..pi/wf/<task-id>` must show exactly one commit; otherwise it is an integration failure
     ("expected one commit, found N").
   - `cd <integration> && git -c commit.gpgsign=false cherry-pick pi/wf/<task-id>`, then the ticket's verification command.
   - **Conflict:** `git cherry-pick --abort`. **Verification fails:** `git reset --keep HEAD~1` (prompts the user).
   - **Integration failure:** if the ticket's notes already contain `integration retry`, it is stuck (step 9).
     Otherwise `bd update <id> --status open --append-notes "integration retry 1: <reason>"` — it comes back in the
     next wave from the new integration head, with the reason added to its description.
   - Success: `bd close <id> --reason "<one line: what landed, reviews passed>"` and
     `bd update <epic-id> --append-notes "landed <id>"` (the audit covers only landed tickets).
9. **Stuck** (`verdict: "stuck"` or a second integration failure):
   `bd update <id> --append-notes "stuck: <blocking findings or failure summary>"`. Do not close; leave it in progress
   and add it to the set-aside list. Only its dependents wait on it.
10. **Clean up** each task worktree: `git worktree remove --force <repo>/.pi/worktrees/<task-id>` (untracked build output is
    expected; the branch keeps the commit until landing).
11. Loop. No pauses or check-ins between waves.

**Stop early only for:** infrastructure failure (`workflow` tool missing, bd/git errors), all remaining tickets stuck or
blocked, or acceptance criteria no reviewer can judge — flag that ticket and continue the rest.

**Resume** (integration worktree already exists):
1. **Live waves:** if any task worktrees exist under `<repo>/.pi/worktrees/` (other than `epic-*`), ask the user once
   whether another session is still running a wave for this epic. Yes → stop. No → remove them all with
   `git worktree remove --force` (a crash left them).
2. **Set-aside list:** rebuild it from notes — tickets whose notes contain `stuck:` or `edits submodule` stay set aside
   and are not noted again.
3. **Landed:** an in-progress ticket whose `wave started: <subject>` note is in `git log --format=%s <BASE>..pi/epic/<epic-id>`,
   or whose commit `git cherry pi/epic/<epic-id> pi/wf/<task-id>` marks `-`, already landed → `bd close` it and note
   `landed <id>` on the epic. The ticket audit re-runs its verification.
4. **Everything else in progress** returns to the candidate queue (`-B` resets its branch). Coder threads are not
   journaled, so `resumeFromRunId` gains nothing here.

## 3. Audit (every run)

`workflow({ script: <references/audit.js>, args: { integrationPath, base: BASE, tickets: [closed tickets: { id, title,
acceptance, verify }], epic: { id, description, planPath } } })` — tickets = those noted `landed <id>` on the epic.

- A ticket `not-met`: reopen it (`bd update <id> --status open --append-notes "audit: <evidence>"`). Report it; do not re-run.
- A ticket `unknown` or `epic: null`: the auditor produced no verdict — report it as unaudited; never reopen for it.
- Epic `missing` / `outOfScope` / `contradicted`: report; never auto-fix.

## 4. Present and land

Present, then stop and wait:

```
Epic <id> — <N> waves

| Commit | Ticket | Title | Reviews | Verification | Audit |
|---|---|---|---|---|---|
| <sha> | <id> | <title> | pass (retries: n; missing: reviewer?) | pass | met / not-met / unknown |

Stuck: <id — last blocking findings>
Set aside: <id — submodule path / human task>
Epic audit: missing [...], out of scope [...], contradicted [...]

git log --stat <BASE>..pi/epic/<epic-id>
```

On the user's go-ahead, land on their active branch with signing (one signature prompt per commit):
`cd <repo> && git cherry-pick <BASE>..pi/epic/<epic-id>`. If it stops on a conflict (their branch moved since `BASE`),
stop and report the commit; the user resolves (`git cherry-pick --continue`) or aborts. Never resolve it yourself.
Then clean up: `git worktree remove --force <repo>/.pi/worktrees/epic-<epic-id>`, `git branch -D pi/epic/<epic-id>` and each
landed `pi/wf/<task-id>`. List the branches left behind (stuck, set aside). If they decline, leave everything in place.

## Rules

- **Never run the `pi` binary** and never tell a subagent to.
- **Children are hermetic:** no MCP, codemode, web tools, or user extensions; they do have the skills catalog. Put
  everything a coder needs in the ticket text.
- **Findings severity:** `critical` and `important` block and trigger a retry (max 2, inside `wave.js`); `suggestion`
  never blocks — list them in the presentation.
- **Commit messages** describe the change, never the process ("address review findings").
