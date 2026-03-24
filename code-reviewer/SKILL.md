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

### Re-Review (Verifying a Fix)

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
- `Plan/spec`: a file path when a spec exists; `"none"` for ad-hoc reviews
- `Review focus`: the reviewer's domain — one per reviewer
- `Worktree`: absolute path to the coder's worktree for automated review; `"n/a"` for manual review
- `Prior findings to verify`: paste the full finding block(s) from the original review output so the reviewer has exact context; use `"initial review"` on the first pass

---

## Review Loop

This is the core orchestration logic. Follow it precisely.

### Cycle Structure

**Step 1 — Initial round:** Spawn all four reviewers in parallel. Each receives:
- The full branch diff (base to HEAD)
- The plan/spec reference (file path or inline content), if available
- `Prior findings to verify: initial review`

If the initial round produces no blocking findings, exit immediately — no fix cycle or final sweep is needed.

Reviewers run independently in their own context windows. They do not share context with each other. Each reviewer gathers additional context (codebase samples, dependency info, etc.) using its own tools.

**Step 2 — Fix cycle:** Address blocking findings. Fix all blocking findings from a given reviewer, then re-run that reviewer once to verify all fixes in that domain. Once all targeted re-reviews pass, proceed to the final sweep. Each re-run receives:
- The full branch diff (base to HEAD, now including the fixes)
- The specific finding(s) being verified (pasted in full from the original output)

The reviewer confirms the findings are resolved and checks that the fixes did not introduce new issues within its domain.

**Step 3 — Final sweep:** Run all four reviewers again on the full branch diff (base to HEAD, including all fixes). This catches cross-domain issues introduced by the fixes.

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

Issue all four as tool calls in a single message so they run in parallel. These are tool invocations — not code output. Use the `task` tool with the appropriate subagent type for each. The subagent types (`correctness-reviewer`, `failure-path-reviewer`, `readability-reviewer`, `security-reviewer`) are registered agent types in the platform.

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

**All four run on every review pass — no conditional skipping.**

For manual review, set `Worktree: n/a` in each prompt.

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
