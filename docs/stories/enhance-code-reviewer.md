# Story: Enhance code-reviewer with Review Principles

## Source
Brainstorm: Grug Brain Philosophy Integration
Behaviors covered:
- Chesterton's Fence as a review principle: don't recommend removing code you don't understand
- FOLD (Fear of Looking Dumb): "I don't understand this" is a legitimate, high-signal finding

## Summary
Add two complementary review principles to the code-reviewer skill. Chesterton's Fence prevents reviewers from recommending removal of code whose purpose they haven't understood. FOLD normalizes "I don't understand this" as a quality signal rather than a reviewer weakness.

## Acceptance Criteria
- [ ] Chesterton's Fence is added as a review principle: before recommending removal or rewrite of any code, the reviewer must be able to articulate why the code was there in the first place. "I don't understand this" is not a valid reason to remove -- it's a reason to investigate
- [ ] FOLD is added as an explicit norm: "I don't understand this and that concerns me" is a legitimate, high-signal review comment. If a reviewer cannot understand the code, that's information about the code's complexity, not the reviewer's competence
- [ ] Both principles are positioned where the sub-reviewers (correctness, failure-path, readability, security) will apply them -- not buried in orchestration-only sections
- [ ] The two principles are presented as complementary: Chesterton's Fence says "don't tear down what you don't understand," FOLD says "it's okay to admit you don't understand"
- [ ] Existing review workflow (4-reviewer pipeline, cycle counting, severity classification) is not modified

## Open Questions
- None.

## Out of Scope
- Adding an escape hatch for simple changes to skip reviewers (separate concern from these principles)
- Modifying the sub-reviewer agent prompts themselves (this story adds principles to the skill; agent prompt updates are a follow-up if needed)
