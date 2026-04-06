# Story: Enhance python-design with Generics Restraint

## Source
Brainstorm: Grug Brain Philosophy Integration
Behaviors covered:
- Generics are most valuable in container/collection abstractions; over-genericizing is a common complexity trap

## Summary
Add a generics restraint note to the python-design skill near the existing generics and advanced typing content. The current treatment is neutral; this adds an opinionated warning about where generics add value versus where they introduce unnecessary complexity.

## Acceptance Criteria
- [ ] Guidance is added near existing generics/typing content stating that generics are most valuable in container and collection abstractions
- [ ] Warns that the temptation to over-genericize is a common complexity trap -- making code more abstract than the problem requires
- [ ] Does not discourage generics wholesale -- the guidance distinguishes high-value use (containers, type-safe collections, reusable data structures) from low-value use (genericizing business logic that has one concrete type)
- [ ] Integrates naturally into the existing skill structure rather than appearing as a standalone warning block

## Open Questions
- None.

## Out of Scope
- Rewriting the existing generics/typing section
- Adding generics guidance to the language-agnostic software-design skill (grug's point is general, but the actionable guidance is Python-specific here)
