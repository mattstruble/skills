---
name: "orchestrator"
summary: "Execute a planned beads epic in waves: coder plus fast-review tier in worktrees via a workflow script, deferred findings caught by pipelined wave-end deep review and an epic-end deep sweep, then audits"
type: "process"
description: "Load when the user wants to execute a planned epic — when they say 'orchestrate', 'execute this epic', 'run the tasks', 'kick off the epic', or 'run the plan'. Also load when the frontier of a beads epic is ready and the user wants autonomous execution. NOT for planning (see planner), NOT for brainstorming (see brainstorm), NOT for code review of a single PR. Requires the `workflow` tool (pi-dynamic-workflows) — stop if it is unavailable."
metadata:
  route-prompt: "orchestrat* execute*epic run*the*tasks kick*off*the*epic run*the*plan"
---

# Orchestrator

Drive a beads epic from its first ready ticket to an audited set of commits on the user's working branch. Coders and
reviewers run as subagents inside a workflow script; you own beads, git integration, verification, and governance.
Each ticket that passes review lands on the working branch immediately, with its review summary in the commit body,
so the user reviews the whole run with `git diff origin/<branch>`.

<HARD-GATE>
Never edit, write, or create files yourself — every change comes from a coder in its own worktree. Bash is for
`bd`, the git integration commands below, and verification commands from tickets. Never push. A permission denial
is final: do not work around it; record it for the summary's **Needs approval** section.
</HARD-GATE>

## Layout

| Thing | Where |
|---|---|
| Working branch | the user's current branch in `<repo>` (`git rev-parse --show-toplevel`); passed tickets land here |
| Task worktree | `<repo>/.pi/worktrees/<task-id>` on branch `pi/wf/<task-id>`, cut from the working branch `HEAD` |
| Wave script | saved workflow `orchestrator_wave` (source: `references/wave.js`) |
| Strong-pass script | saved workflow `orchestrator_strong_pass` (source: `references/strong-pass.js`) — wave mode (delta, pipelined) and epic mode (final gate) |
| Audit script | saved workflow `orchestrator_audit` (source: `references/audit.js`) |
| Agent profiles | `coder`, `correctness-reviewer`, `failure-path-reviewer`, `readability-reviewer`, `security-reviewer`, `ticket-auditor`, `epic-auditor` |
| Model tiers | from the host's model map: `coder` and `deep-reviewer` on the strong model, `fast-reviewer` on the fast parallel model. The scripts pin tiers by name; never pin a model inline |

Pass **absolute** paths (`<repo>/.pi/worktrees/...`, `<repo>`) as `worktreePath` / `integrationPath`; agent `cwd` must be
absolute. Run both scripts with `workflow({ name: "orchestrator_wave" | "orchestrator_audit", background: false, args })`
so the result returns in the same turn. Call `workflow` directly as a tool, never from codemode: nested calls hide the
workflow progress panel (guardrails blocks them). If the saved workflow is missing, pass the reference file's full text
as `script` instead. Always write beads notes with `--append-notes` (`--notes` refuses to overwrite existing notes).

Integration commits are unsigned (`-c commit.gpgsign=false`) so an unattended run never waits on a signing prompt; the
final summary gives the user the optional `git sign-unpushed` command for signing before a push.

## 1. Start

1. `bd show <epic-id>`: the description must link a plan or design note. If none, warn the user once and continue —
   the epic audit then judges against the description and tickets only.
2. **Clean tree:** `git -C <repo> status --porcelain --untracked-files=no` must be empty. Otherwise stop and ask the user
   to commit or stash: cherry-picks into a dirty checkout fail. Tell them not to edit the checkout during the run.
3. If the epic notes contain `orchestrator base=`, you are resuming: read `BASE` from them, run **Resume** below, then
   continue with the waves (or straight to the epic-end sweep if nothing is runnable).
4. Otherwise `bd ready --parent <epic-id>`. Empty frontier: report the state (no children, all blocked, all closed) and stop.
5. Record `BASE=$(git -C <repo> rev-parse HEAD)` and `BRANCH=$(git -C <repo> branch --show-current)`, then
   `bd update <epic-id> --append-notes "orchestrator base=<BASE> branch=<BRANCH>"`.
6. Submodule paths, once: `git config -f <repo>/.gitmodules --get-regexp '\.path$'` (missing file = none).

## 2. Each wave

1. **Candidates:** `bd ready --parent <epic-id>` plus any tickets Resume returned to the queue, minus the set-aside list. Set aside `[human-task]`,
   `[research]`, `[brainstorming]`, `[prototype]` tickets.
2. **Submodule filter:** tickets naming paths inside a submodule (from Start step 6) are set aside, once:
   `bd update <id> --append-notes "edits submodule <path>; run in the main checkout"`.
   Set-aside tickets stay in the list for the summary and are never re-noted.
   **No runnable candidates left → go to the epic-end sweep (section 3).**
3. **File conflicts:** two candidates naming the same file go in different waves (keep the first). Tickets back for an
   integration retry run at most one per wave: they already collided once, and siblings retried together collide again.
   **Wave size: up to two tickets.** The wave script staggers their Code phases (the second coder starts when the first
   finishes), so one coder decodes at a time while the first task's fast review runs on the other model. Three or more
   tickets in a wave serialize coders for no gain.
4. **Claim** each candidate (`bd update <id> --claim`); skip any that fail.
5. **Commit message:** write one conventional-commit subject per ticket from its title and intent (git-commit skill rules:
   type(scope): imperative, lowercase, < 72 chars, no ticket IDs). `wave.js` adds the review summary as the body.
6. **Worktrees:** for each ticket,
   `cd <repo> && git worktree add -B pi/wf/<task-id> .pi/worktrees/<task-id> HEAD` (`-B` resets a branch left by an
   earlier attempt); note the working-branch `HEAD` SHA as that task's `base`.
7. **Run the wave:** `bd update <id> --append-notes "wave started: <commitMessage>"` for each ticket, then
   `workflow({ name: "orchestrator_wave", background: false, concurrency: 4, args: { tasks: [{ id, title, description,
   acceptance, commitMessage, verify, worktreePath, branch, base }] } })`. `verify` is the command from the acceptance criteria
   (tests/build), or empty. For integration retries, append the previous failure output to `description`.
   **`concurrency: 4` is mandatory, never omit it.** A session left to its own choice once picked 1 and every reviewer ran
   back-to-back — a 4-reviewer pass took 43 minutes instead of ~12, and the session imitated its own mistake for every
   wave after. The fleet measured fine with four interleaved streams; there is nothing to protect.
   A `null` entry in `results` (that task's agent call failed outright) maps back to its task by index: treat it as stuck.
8. **Land** each `pass` **or `deferred`** result on the working branch, one at a time
   (`deferred` = blocking findings survived the fast loop's one retry; the strong pass judges them — the commit body
   already lists them under "deferred to the strong pass"):
   - **Before the wave's first cherry-pick:** `git -C <repo> branch --show-current` must equal `BRANCH`, and
     `git -C <repo> status --porcelain --untracked-files=no` must be empty. If either check fails, land nothing: keep
     the passed worktrees and `pi/wf/*` branches (skip step 10 for them), note `not landed: <reason>` on each ticket,
     stop the run, and report the reason and the kept branches in the summary.
   - `git -C <repo> log --oneline <base>..pi/wf/<task-id>` must show exactly one commit; otherwise it is an integration
     failure ("expected one commit, found N").
   - `cd <repo> && git -c commit.gpgsign=false cherry-pick pi/wf/<task-id>`, then the ticket's verification command in `<repo>`.
   - **Conflict:** `git cherry-pick --abort`. **Verification fails:** `git reset --keep HEAD~1`.
   - **Integration failure:** if the ticket's notes already contain `integration retry`, it is stuck (step 9).
     Otherwise `bd update <id> --status open --append-notes "integration retry 1: <reason>"` — it comes back in the
     next wave from the new `HEAD`, with the reason added to its description.
   - Success: `bd close <id> --reason "<one line: what landed, reviews passed>"` and
     `bd update <epic-id> --append-notes "landed <id> <short sha>"` (the audit covers only landed tickets). For a
     `deferred` result, also note `deferred findings: <one line>` on the epic — the strong pass owns them from here.
9. **Stuck** (`verdict: "stuck"` — infrastructure failure only: agent timeout, provider error — or a second integration
   failure):
   `bd update <id> --append-notes "stuck: <failure summary>"`. Do not close; leave it in progress
   and add it to the set-aside list. Only its dependents wait on it.
10. **Clean up** every task of the wave as soon as it is decided (landed, stuck, or sent back for retry):
    `git -C <repo> worktree remove --force <repo>/.pi/worktrees/<task-id>` (untracked build output is expected), then
    `git -C <repo> branch -D pi/wf/<task-id>` — one branch per command (multi-branch deletes prompt). A stuck ticket's
    findings live in its notes; its branch is not kept.
11. **Strong pass (wave mode), after every wave's tickets are decided:**
   `STRONG_SINCE=$(last SHA noted as "orchestrator strong=", or BASE)` then
   `workflow({ name: "orchestrator_strong_pass", background: true, args: { integrationPath: <repo>, mode: "wave", since: STRONG_SINCE } })`.
   Note the runId it returns. Then record the SHA it will cover as pending:
   `bd update <epic-id> --append-notes "orchestrator strong-pending <runId> since=$(git -C <repo> rev-parse HEAD)"`.
   It runs pipelined with the next wave — do not wait for it. **Never rely on the result being delivered into the conversation: an orchestrator mid-wave is never idle and idle-delivery times out.**
   **Retrieve the result yourself at every wave boundary** (step 1 of the next wave, before candidates):
   ```bash
   python3 -c '
   import json,sys
   for l in reversed(open(sys.argv[1]).readlines()):
     d=json.loads(l); s=d.get("delta",{}).get("set",{})
     if s.get("status")=="completed": print(json.dumps(s.get("result"))); break
   ' ~/.pi/workflows/projects/*/runs/<runId>.events.jsonl
   ```
   No output or `running` → still going: proceed with the wave, check again at the next boundary. A result consumed:
   - **critical finding → preempt:** create the fix ticket, put it first in this wave's candidates, and set aside
     tickets that touch the same files until the fix lands. Building on broken ground compounds.
   - **important finding → fix ticket:** normal candidate for the next wave.
   - **suggestion → note** it on the epic; it never blocks.
   Then convert the pending note: `bd update <epic-id> --append-notes "orchestrator strong=<sha> (clean | N findings)"`.
12. Loop. No pauses or check-ins between waves.

**Stop early only for:** infrastructure failure (`workflow` tool missing, bd/git errors), all remaining tickets stuck or
blocked, or acceptance criteria no reviewer can judge — flag that ticket and continue the rest.

**Resume** (epic notes contain `orchestrator base=`): read `BRANCH` from the same note (older notes without it: use
the current branch and note `orchestrator branch=<BRANCH>`).
1. **Live waves:** if any task worktrees exist under `<repo>/.pi/worktrees/`, ask the user once whether another session
   is still running a wave for this epic. Yes → stop. No → remove them and their `pi/wf/*` branches (a crash left them).
2. **Set-aside list:** rebuild it from notes — tickets whose notes contain `stuck:` or `edits submodule` stay set aside
   and are not noted again.
3. **Landed:** an in-progress ticket whose `wave started: <subject>` note is in `git -C <repo> log --format=%s <BASE>..HEAD`
   already landed → `bd close` it and note `landed <id>` on the epic. The ticket audit re-runs its verification.
4. **Everything else in progress** returns to the candidate queue. Coder threads are not journaled, so
   `resumeFromRunId` gains nothing here.
5. **Strong-pass pointer:** the last `orchestrator strong=<sha>` note stands — the next wave-mode pass covers from
   there. If the notes carry a `strong-pending <runId>`, retrieve that run's result first (step 11's journal command).
   If commits landed that the recorded strong SHA does not cover, launch a wave-mode strong pass at Resume
   instead of waiting for the next wave.

## 3. Epic-end sweep, then Audit

With no runnable candidates left, run the final deep gate **before** the audit:

`workflow({ name: "orchestrator_strong_pass", background: false, args: { integrationPath: <repo>, mode: "epic", base: BASE } })`.

- Clean (no blocking findings) → proceed to Audit.
- Blocking findings → one fix ticket per finding (critical first), run them through waves 2–11 as a normal wave loop,
  then re-run the epic sweep. Converge or stop after **two** sweep rounds: surface the remaining findings to the user
  instead of grinding — they decide fix-vs-accept.

Then `workflow({ name: "orchestrator_audit", background: false, args: { integrationPath: <repo>, base: BASE, tickets: [landed
tickets: { id, title, acceptance, verify }], epic: { id, description, planPath } } })` — tickets = those noted
`landed <id>` on the epic.

- A ticket `not-met`: reopen it (`bd update <id> --status open --append-notes "audit: <evidence>"`). Report it; do not re-run.
- A ticket `unknown` or `epic: null`: the auditor produced no verdict — report it as unaudited; never reopen for it.
- Epic `missing` / `outOfScope` / `contradicted`: report; never auto-fix.

## 4. Summary

The work is already on the working branch. End with:

```
Epic <id> — <N> waves, <M> commits on <branch> since <BASE>

| Commit | Ticket | Title | Reviews | Verification | Audit |
|---|---|---|---|---|---|
| <sha> | <id> | <title> | pass (retries: n; missing: reviewer?) | pass | met / not-met / unknown |

Stuck: <id — last failure summary>
Set aside: <id — submodule path / human task>
Needs approval: <ticket — action that was denied or deferred, from child reports and denied integration commands>
Strong passes: <N> wave passes (<range covered>), epic sweep <clean | N blocking fixed | unresolved after 2 rounds>
Epic audit: missing [...], out of scope [...], contradicted [...]

Review:  git diff origin/<branch>   (or git log --stat <BASE>..HEAD; each commit body carries its review summary)
Undo:    git reset --keep <BASE>
Sign:    git sign-unpushed   (optional, before you push)
```

The run never pushes. List every **Needs approval** item, or write `none`.

Confirm `git -C <repo> worktree list` shows no `.pi/worktrees/` entries and `git -C <repo> branch --list 'pi/wf/*'` is empty.

## Rules

- **Never run the `pi` binary** and never tell a subagent to.
- **Children:** subagents load skill-router, guardrails, audit, rtk and pi-permission-system, but no MCP, codemode,
  or web tools. Put everything a coder needs in the ticket text. Deny rules hold in children, and an `ask` is denied
  at once (no prompt): a coder that reports a denied or deferred action goes into **Needs approval**, and the ticket
  text must not depend on ask-tier commands (push, `rm`, `ssh`, cluster writes).
- **Findings severity:** in the fast loop, `critical` and `important` block and trigger exactly one retry (inside
  `wave.js`); whatever survives defers to the strong pass — `suggestion` never blocks and is listed in the commit body.
  In the strong pass, `critical` preempts the next wave's queue and `important` becomes a fix ticket.
- **Commit subjects** describe the change, never the process ("address review findings"). The body is the review summary.
- **Never drop `concurrency: 4`** from the wave call, and never pin models inline — tiers come from the host's model map.
