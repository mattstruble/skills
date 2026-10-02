---
name: "orchestrator"
summary: "Execute a planned beads epic in waves: coders and reviewers in worktrees via a workflow script, each passed ticket cherry-picked onto the working branch, then audits"
type: "process"
description: "Load when the user wants to execute a planned epic — when they say 'orchestrate', 'execute this epic', 'run the tasks', 'kick off the epic', or 'run the plan'. Also load when the frontier of a beads epic is ready and the user wants autonomous execution. NOT for planning (see planner), NOT for brainstorming (see brainstorm), NOT for code review of a single PR. Requires the `workflow` tool (pi-dynamic-workflows) — stop if it is unavailable."
---

# Orchestrator

Drive a beads epic from its first ready ticket to an audited set of commits on the user's working branch. Coders and
reviewers run as subagents inside a workflow script; you own beads, git integration, verification, and governance.
Each ticket that passes review lands on the working branch immediately, with its review summary in the commit body,
so the user reviews the whole run with `git diff origin/<branch>`.

<HARD-GATE>
Never edit, write, or create files yourself — every change comes from a coder in its own worktree. Bash is for
`bd`, the git integration commands below, and verification commands from tickets. Never push. `git commit` and
`git reset` go through the user's permission prompts; do not work around them.
</HARD-GATE>

## Layout

| Thing | Where |
|---|---|
| Working branch | the user's current branch in `<repo>` (`git rev-parse --show-toplevel`); passed tickets land here |
| Task worktree | `<repo>/.pi/worktrees/<task-id>` on branch `pi/wf/<task-id>`, cut from the working branch `HEAD` |
| Wave script | saved workflow `orchestrator_wave` (source: `references/wave.js`) |
| Audit script | saved workflow `orchestrator_audit` (source: `references/audit.js`) |
| Agent profiles | `coder`, `correctness-reviewer`, `failure-path-reviewer`, `readability-reviewer`, `security-reviewer`, `ticket-auditor`, `epic-auditor` |

Pass **absolute** paths (`<repo>/.pi/worktrees/...`, `<repo>`) as `worktreePath` / `integrationPath`; agent `cwd` must be
absolute. Run both scripts with `workflow({ name: "orchestrator_wave" | "orchestrator_audit", background: false, args })`
so the result returns in the same turn. Call `workflow` directly as a tool, never from codemode: nested calls hide the
workflow progress panel (guardrails blocks them). If the saved workflow is missing, pass the reference file's full text
as `script` instead. Always write beads notes with `--append-notes` (`--notes` refuses to overwrite existing notes).

Integration commits are unsigned (`-c commit.gpgsign=false`) so an unattended run never waits on a signing prompt; the
final summary gives the user the one-line re-sign command.

## 1. Start

1. `bd show <epic-id>`: the description must link a plan or design note. If none, warn the user once and continue —
   the epic audit then judges against the description and tickets only.
2. **Clean tree:** `git -C <repo> status --porcelain --untracked-files=no` must be empty. Otherwise stop and ask the user
   to commit or stash: cherry-picks into a dirty checkout fail. Tell them not to edit the checkout during the run.
3. If the epic notes contain `orchestrator base=`, you are resuming: read `BASE` from them, run **Resume** below, then
   continue with the waves (or straight to Audit if nothing is runnable).
4. Otherwise `bd ready --parent <epic-id>`. Empty frontier: report the state (no children, all blocked, all closed) and stop.
5. Record `BASE=$(git -C <repo> rev-parse HEAD)` and `bd update <epic-id> --append-notes "orchestrator base=<BASE>"`.
6. Submodule paths, once: `git config -f <repo>/.gitmodules --get-regexp '\.path$'` (missing file = none).

## 2. Each wave

1. **Candidates:** `bd ready --parent <epic-id>` plus any tickets Resume returned to the queue, minus the set-aside list. Set aside `[human-task]`,
   `[research]`, `[brainstorming]`, `[prototype]` tickets.
2. **Submodule filter:** tickets naming paths inside a submodule (from Start step 6) are set aside, once:
   `bd update <id> --append-notes "edits submodule <path>; run in the main checkout"`.
   Set-aside tickets stay in the list for the summary and are never re-noted.
   **No runnable candidates left → go to Audit.**
3. **File conflicts:** two candidates naming the same file go in different waves (keep the first). Tickets back for an
   integration retry run at most one per wave: they already collided once, and siblings retried together collide again.
4. **Claim** each candidate (`bd update <id> --claim`); skip any that fail.
5. **Commit message:** write one conventional-commit subject per ticket from its title and intent (git-commit skill rules:
   type(scope): imperative, lowercase, < 72 chars, no ticket IDs). `wave.js` adds the review summary as the body.
6. **Worktrees:** for each ticket,
   `cd <repo> && git worktree add -B pi/wf/<task-id> .pi/worktrees/<task-id> HEAD` (`-B` resets a branch left by an
   earlier attempt); note the working-branch `HEAD` SHA as that task's `base`.
7. **Run the wave:** `bd update <id> --append-notes "wave started: <commitMessage>"` for each ticket, then
   `workflow({ name: "orchestrator_wave", background: false, args: { tasks: [{ id, title, description, acceptance,
   commitMessage, verify, worktreePath, branch, base }] } })`. `verify` is the command from the acceptance criteria
   (tests/build), or empty. For integration retries, append the previous failure output to `description`.
   A `null` entry in `results` (that task's agent call failed outright) maps back to its task by index: treat it as stuck.
8. **Land** each `pass` result on the working branch, one at a time:
   - `git -C <repo> log --oneline <base>..pi/wf/<task-id>` must show exactly one commit; otherwise it is an integration
     failure ("expected one commit, found N").
   - `cd <repo> && git -c commit.gpgsign=false cherry-pick pi/wf/<task-id>`, then the ticket's verification command in `<repo>`.
   - **Conflict:** `git cherry-pick --abort`. **Verification fails:** `git reset --keep HEAD~1` (prompts the user).
   - **Integration failure:** if the ticket's notes already contain `integration retry`, it is stuck (step 9).
     Otherwise `bd update <id> --status open --append-notes "integration retry 1: <reason>"` — it comes back in the
     next wave from the new `HEAD`, with the reason added to its description.
   - Success: `bd close <id> --reason "<one line: what landed, reviews passed>"` and
     `bd update <epic-id> --append-notes "landed <id> <short sha>"` (the audit covers only landed tickets).
9. **Stuck** (`verdict: "stuck"` or a second integration failure):
   `bd update <id> --append-notes "stuck: <blocking findings or failure summary>"`. Do not close; leave it in progress
   and add it to the set-aside list. Only its dependents wait on it.
10. **Clean up** every task of the wave as soon as it is decided (landed, stuck, or sent back for retry):
    `git -C <repo> worktree remove --force <repo>/.pi/worktrees/<task-id>` (untracked build output is expected), then
    `git -C <repo> branch -D pi/wf/<task-id>` — one branch per command (multi-branch deletes prompt). A stuck ticket's
    findings live in its notes; its branch is not kept.
11. Loop. No pauses or check-ins between waves.

**Stop early only for:** infrastructure failure (`workflow` tool missing, bd/git errors), all remaining tickets stuck or
blocked, or acceptance criteria no reviewer can judge — flag that ticket and continue the rest.

**Resume** (epic notes contain `orchestrator base=`):
1. **Live waves:** if any task worktrees exist under `<repo>/.pi/worktrees/`, ask the user once whether another session
   is still running a wave for this epic. Yes → stop. No → remove them and their `pi/wf/*` branches (a crash left them).
2. **Set-aside list:** rebuild it from notes — tickets whose notes contain `stuck:` or `edits submodule` stay set aside
   and are not noted again.
3. **Landed:** an in-progress ticket whose `wave started: <subject>` note is in `git -C <repo> log --format=%s <BASE>..HEAD`
   already landed → `bd close` it and note `landed <id>` on the epic. The ticket audit re-runs its verification.
4. **Everything else in progress** returns to the candidate queue. Coder threads are not journaled, so
   `resumeFromRunId` gains nothing here.

## 3. Audit (every run)

`workflow({ name: "orchestrator_audit", background: false, args: { integrationPath: <repo>, base: BASE, tickets: [landed
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

Stuck: <id — last blocking findings>
Set aside: <id — submodule path / human task>
Epic audit: missing [...], out of scope [...], contradicted [...]

Review:  git diff origin/<branch>   (or git log --stat <BASE>..HEAD; each commit body carries its review summary)
Re-sign: git rebase --exec 'git commit --amend --no-edit -S' <BASE>
```

Confirm `git -C <repo> worktree list` shows no `.pi/worktrees/` entries and `git -C <repo> branch --list 'pi/wf/*'` is empty.

## Rules

- **Never run the `pi` binary** and never tell a subagent to.
- **Children:** subagents load skill-router, guardrails, audit and rtk, but no MCP, codemode, or web tools. Put
  everything a coder needs in the ticket text.
- **Findings severity:** `critical` and `important` block and trigger a retry (max 2, inside `wave.js`); `suggestion`
  never blocks — `wave.js` lists them in the commit body.
- **Commit subjects** describe the change, never the process ("address review findings"). The body is the review summary.
