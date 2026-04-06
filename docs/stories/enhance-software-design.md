# Story: Enhance software-design with Pragmatic Design Principles

## Source
Brainstorm: Grug Brain Philosophy Integration
Behaviors covered:
- Chesterton's Fence: understand why code exists before removing it
- Locality of Behavior: behavior should be obvious by looking at the code unit
- Let cut points emerge: don't factor early; wait for natural boundaries
- Expression complexity: break complex conditionals into named intermediates
- Layered interfaces: simple API for simple cases, complex API when needed

## Summary
Add five pragmatic design principles to the existing software-design skill, integrating them into the current structure without bloating or duplicating existing content. Each addition addresses a specific gap identified by cross-referencing the skill against grug brain philosophy.

## Acceptance Criteria
- [ ] Chesterton's Fence is added as a principle: existing code earned its place; understand why it exists before removing or rewriting it. Positioned as the complement to "every piece of code must earn its place" (new code earns entry, existing code has already earned presence)
- [ ] Locality of Behavior is added: the behavior of a code unit should be obvious by looking at that unit. Complements the existing "honesty" principle but addresses structural proximity, not just naming
- [ ] "Let cut points emerge" is added: bias toward waiting for natural factoring boundaries to reveal themselves through experience rather than imposing abstractions early. Refines the existing "start minimal" / "resist speculative abstractions" guidance with a more concrete framing
- [ ] Expression complexity guidance is added: break complex conditionals into named intermediate variables for debuggability and readability. Includes a before/after example
- [ ] Layered interfaces is added as a refinement of the existing "caller's perspective" principle: design simple interfaces for common cases, with more complex interfaces available for power users
- [ ] No existing content is removed or contradicted
- [ ] SKILL.md stays under 500 lines after additions
- [ ] Each addition integrates naturally into the existing skill structure rather than appearing as a bolted-on appendix

## Open Questions
- None.

## Out of Scope
- Language-specific expression complexity patterns (covered by python-design where relevant)
- Full treatment of refactoring strategy (Chesterton's Fence is a principle, not a refactoring workflow)
