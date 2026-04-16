---
name: code-reviewer
description: "Use when reviewing PRs, examining code changes, running `gh pr diff`, or when asked for code review. Also trigger after completing a feature implementation when review is needed before merging. NOT for test quality (see test-design)."
author: mattstruble
---

# Code Review Orchestration

This skill orchestrates a four-reviewer code review pipeline. Spawn all four specialized reviewers in parallel, aggregate their findings, drive the fix cycle, and report results. The skill covers two entry points: manual review (user-driven) and automated post-implementation review (coder-driven).

---

## Entry Points

### Manual Review

Triggered when a user or agent requests a review (e.g., "review PR #42", "review this diff").

1. Gather the diff:
   - PR: `gh pr diff <N>`
   - Branch range: `git diff <base>..<HEAD>`
   - Inline: use the diff content provided in the conversation
2. Spawn all four reviewers in parallel (see [Spawning Instructions](#spawning-instructions))
3. Aggregate findings into a structured report (see [Aggregating Results](#aggregating-results))
4. Present findings to the user. The user decides which findings to address and makes fixes themselves (or directs the calling agent to fix).
5. After fixes are made, re-run targeted reviewers on affected findings, then run a final sweep with all four.
6. On convergence or after 3 full cycles, report all remaining findings (blocking and non-blocking) and wait for the user to decide: fix remaining findings, accept them as known issues, or close the review.

A **cycle** in manual review is one round of user-directed fixes followed by a final sweep. The 3-cycle cap applies the same way as in automated review.

**Inline-diff reviews:** When the user pastes a diff with no underlying git range, re-reviews use the updated inline diff rather than a git range. The user or calling agent must provide the updated inline diff content after each fix, since there is no git range to re-run.

### Automated Post-Implementation Review

Triggered by the coder agent after completing implementation.

1. Gather the diff from the coder's changes (typically `git diff <base>..<HEAD>` in the worktree)
2. Spawn all four reviewers in parallel
3. Aggregate findings
4. Coder fixes all blocking findings
5. Re-run the originating reviewer(s) to verify each fix
6. Run a final sweep with all four reviewers
7. Exit when all four return clean, or after 3 full cycles surface remaining findings to the coder — they must decide whether to fix them, accept them as known issues, or escalate to the user

---

## Review Request Template

Use this template when spawning each reviewer. Populate all fields before spawning.

### Initial Review

```
## Review Request

**Diff source:** <gh pr diff N | git diff base..HEAD | inline diff>
**Plan/spec:** <file path to spec, or "none">
**Review focus:** <correctness | failure-path | readability | security>
**Worktree:** <absolute path to worktree, or "n/a" for manual review>
**Prior findings to verify:** initial review
```

### Verification Resume (Step 2 — Fix Cycle)

Used when resuming a reviewer via `task_id` to verify its prior blocking findings were addressed. The reviewer already has its findings in context from the initial round — no need to restate them.

```
## Verification Re-Review

**Diff source:** git diff base..HEAD
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/

Verify your prior blocking findings against the current diff. Confirm each was addressed and check that the fixes did not introduce new issues within your domain.
```

### Final Sweep Resume (Step 3)

Used when resuming all reviewers via `task_id` for the final sweep after fixes are complete.

```
## Final Sweep Re-Review

**Diff source:** git diff base..HEAD
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/

The fix cycle is complete. Re-review the full diff (base to HEAD). Focus on areas changed since your initial review — fixes may have introduced new issues. Report any new findings; do not re-report findings that were already addressed.
```

### Fallback Re-Review (Fresh Spawn)

Used when a resumed reviewer fails (error, malformed output, or session cannot be resumed). Falls back to a fresh spawn with full context.

```
## Review Request

**Diff source:** git diff base..HEAD
**Plan/spec:** docs/specs/2026-03-24-feature-design.md
**Review focus:** security
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/
**Prior findings to verify:**
  - **Severity:** critical
    **Blocking:** yes
    **File:** src/auth/handler.py:42
    **Category:** security
    **Description:** Raw string interpolation in SQL query allows injection
    **Recommendation:** Use parameterized queries
```

**Field guidance:**
- `Diff source`: the exact command or label used to produce the diff
- `Plan/spec`: a file path when a spec exists; `"none"` for ad-hoc reviews (initial and fallback templates only)
- `Review focus`: the reviewer's domain (initial and fallback templates only)
- `Worktree`: absolute path to the coder's worktree for automated review; `"n/a"` for manual review
- `Prior findings to verify`: paste the full finding block(s) from the original review output (fallback template only); not needed for resumed sessions since the reviewer retains its prior context

---

## Review Principles

These principles apply when orchestrating reviews and evaluating findings. When spawning sub-reviewers, include these principles in the review request prompt so they are visible to each reviewer.

### Chesterton's Fence

Before recommending removal or rewrite of any code, be able to articulate why the code was there in the first place. "I don't understand this" is not a valid reason to recommend removal — it's a reason to investigate.

This applies especially to:
- Error handling that looks redundant
- Defensive checks that seem unnecessary
- Legacy compatibility code

If you cannot explain the purpose of code you're recommending to remove, downgrade your finding to a suggestion and note that the purpose is unclear. The author may have context you don't.

**Security exception:** This downgrade rule does not apply to security-relevant code. If you cannot explain why a security check, input validation, authentication guard, or rate limit exists, escalate rather than downgrade. The cost of wrongly removing a security defense is asymmetrically higher than preserving unnecessary code.

### FOLD (Fear of Looking Dumb)

"I don't understand this and that concerns me" is a legitimate, high-signal review comment. If you cannot understand a piece of code after a genuine attempt, that's information about the code's complexity — not your competence.

Raise a readability finding when code is genuinely hard to follow, even if you can't articulate exactly what's wrong. "I had to read this three times and I'm still not confident I understand it" is a valid finding.

These two principles are complementary: Chesterton's Fence says *don't tear down what you don't understand*; FOLD says *it's okay to admit you don't understand*.

---

## Review Loop

This is the core orchestration logic. Follow it precisely.

### Cycle Structure

**Step 1 — Initial round:** Spawn all four reviewers in parallel as fresh agents. Each receives:
- The full branch diff (base to HEAD)
- The plan/spec reference (file path or inline content), if available
- `Prior findings to verify: initial review`

**Capture the `task_id` returned by each reviewer.** Maintain a mapping of `{reviewer_type: task_id}` for use in subsequent steps. All reviewer reuse in Steps 2 and 3 depends on these IDs.

If the initial round produces no blocking findings, exit immediately — no fix cycle or final sweep is needed.

Reviewers run independently in their own context windows. They do not share context with each other. Each reviewer gathers additional context (codebase samples, dependency info, etc.) using its own tools.

**Step 2 — Fix cycle:** Address blocking findings. Fix all blocking findings from a given reviewer, then **resume that reviewer via its `task_id`** to verify all fixes in that domain. Use the Verification Resume template — the resumed reviewer already has its prior findings in context, so only provide the updated diff source and verification directive. Once all targeted re-reviews pass, proceed to the final sweep.

**Fallback:** If a resumed reviewer fails (error, malformed output, or session cannot be resumed), discard its `task_id` and fall back to a fresh spawn using the Fallback Re-Review template with the full finding context. Update the `task_id` mapping with the new session ID.

**Step 3 — Final sweep:** **Resume all four reviewers via their `task_id`s** using the Final Sweep Resume template. Each reviewer re-examines the full diff with attention to areas changed by fixes. This catches cross-domain issues introduced during the fix cycle.

**Fallback:** If a resumed reviewer fails, discard its `task_id` and fall back to a fresh spawn using the initial Review Request template. Update the `task_id` mapping with the new session ID for any subsequent cycles.

**Step 4 — Exit conditions:**
- All four return `LGTM: no findings` on the final sweep → review complete
- Three full cycles without convergence → surface remaining findings to the coder — they must decide whether to fix them, accept them as known issues, or escalate to the user

### Cycle Counting

Cycle 1 is the first complete pass through steps 1–3. The counter increments to cycle 2 when cycle 1's final sweep finds new blocking findings, requiring another round of fixes and another final sweep. Escalation triggers when cycle 3's final sweep still has blocking findings.

Individual targeted re-reviews within a fix cycle do **not** increment the counter.

### Non-Blocking Findings

Collect all non-blocking findings (suggestions and non-blocking important findings) across all rounds. Do not address them during the fix cycle. Surface them to the user or coder in the final report for optional action.

Drop non-blocking findings that become stale — if the code they reference was deleted or rewritten during fixes, exclude them from the final report. Only include findings that apply to the final state of the code.

---

## Spawning Instructions

### Initial Round (Fresh Spawn)

Issue all four as tool calls in a single message so they run in parallel. These are tool invocations — not code output. Use the `task` tool with the appropriate subagent type for each. The subagent types (`correctness-reviewer`, `failure-path-reviewer`, `readability-reviewer`, `security-reviewer`) are registered agent types in the platform.

**Capture the `task_id` from each return value.** You need these to resume reviewers in subsequent steps.

```
task(subagent_type="correctness-reviewer", description="Correctness review", prompt="
## Review Request

**Diff source:** git diff main..HEAD
**Plan/spec:** docs/specs/my-feature.md
**Review focus:** correctness
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/
**Prior findings to verify:** initial review
")

task(subagent_type="failure-path-reviewer", description="Failure path review", prompt="
## Review Request

**Diff source:** git diff main..HEAD
**Plan/spec:** docs/specs/my-feature.md
**Review focus:** failure-path
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/
**Prior findings to verify:** initial review
")

task(subagent_type="readability-reviewer", description="Readability review", prompt="
## Review Request

**Diff source:** git diff main..HEAD
**Plan/spec:** docs/specs/my-feature.md
**Review focus:** readability
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/
**Prior findings to verify:** initial review
")

task(subagent_type="security-reviewer", description="Security review", prompt="
## Review Request

**Diff source:** git diff main..HEAD
**Plan/spec:** docs/specs/my-feature.md
**Review focus:** security
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/
**Prior findings to verify:** initial review
")
```

For manual review, set `Worktree: n/a` in each prompt.

### Verification Resume (Step 2)

Resume only the reviewer(s) that reported blocking findings. Use their captured `task_id` to continue the existing session.

```
task(subagent_type="security-reviewer", task_id="<captured_task_id>", description="Verify security fixes", prompt="
## Verification Re-Review

**Diff source:** git diff main..HEAD
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/

Verify your prior blocking findings against the current diff. Confirm each was addressed and check that the fixes did not introduce new issues within your domain.
")
```

### Final Sweep Resume (Step 3)

Resume all four reviewers via their `task_id`s. Issue all four in a single message for parallel execution.

```
task(subagent_type="correctness-reviewer", task_id="<captured_task_id>", description="Final correctness sweep", prompt="
## Final Sweep Re-Review

**Diff source:** git diff main..HEAD
**Worktree:** /tmp/opencode-wt/session-xyz/wave-1-task-1/

The fix cycle is complete. Re-review the full diff (base to HEAD). Focus on areas changed since your initial review — fixes may have introduced new issues. Report any new findings; do not re-report findings that were already addressed.
")
```

Repeat for all four reviewer types with their respective `task_id`s.

### Fallback (Fresh Spawn on Resume Failure)

If resuming a reviewer fails (error, malformed output, or session cannot be resumed), discard the `task_id` and spawn a fresh reviewer using the initial Review Request template (for final sweeps) or the Fallback Re-Review template (for verification, including the prior findings in full). Update the `task_id` mapping with the new session ID.

---

## Aggregating Results

After all four reviewers return:

1. Collect all findings from all four reviewers
2. Separate blocking from non-blocking:
   - **Blocking:** all critical findings; important findings without explicit non-blocking justification in their Recommendation field
   - **Non-blocking:** suggestions; important findings with explicit non-blocking justification in their Recommendation field
3. For **automated review**: fix all blocking findings, then re-run originating reviewers to verify, then run the final sweep
4. For **manual review**: present the full structured report to the user; wait for direction before proceeding

Present findings grouped by severity (critical → important → suggestion), then by reviewer within each group.

---

## Standardized Output Format

Each reviewer uses this format for every finding. The calling agent should expect this structure when parsing results.

```
**Severity:** critical | important | suggestion
**Blocking:** yes | no
**File:** <path>:<line>
**Category:** correctness | failure-path | readability | security
**Description:** <what the issue is>
**Recommendation:** <what to do about it, plus justification if marking
  an important finding as non-blocking>
```

**Blocking rules:**
- `critical` → always blocking
- `important` → blocking by default; non-blocking only with explicit justification in the Recommendation field
- `suggestion` → never blocking

**Clean review:** `LGTM: no findings`

---

## Completion Report Format

For automated post-implementation review, include this block in the coder's completion report:

```
### Review Summary
- Status: clean | escalated (N blocking findings remain)
- Review rounds: [N]
- Total blocking findings addressed: [N]
- Remaining non-blocking findings: [N]
- Findings by reviewer:
  - correctness-reviewer: [N critical, N important, N suggestion]
  - failure-path-reviewer: [N critical, N important, N suggestion]
  - readability-reviewer: [N critical, N important, N suggestion]
  - security-reviewer: [N critical, N important, N suggestion]
```
