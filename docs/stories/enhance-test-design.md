# Story: Enhance test-design with Investment Bias

## Source
Brainstorm: Grug Brain Philosophy Integration
Behaviors covered:
- Integration tests are the sweet spot: high enough to test correctness, low enough to debug
- Mocking should be rare and coarse-grained only

## Summary
Add an opinionated investment bias toward integration tests and strengthen the existing anti-mocking stance in the test-design skill. The existing tradeoff framework (Kent Beck's desiderata) is preserved -- these additions layer a "where to invest" recommendation on top, not a replacement.

## Acceptance Criteria
- [ ] Integration test investment bias is added, framed as "where returns are highest" rather than a blanket prescription. The reasoning: unit tests break on implementation changes (coupled to internals), e2e tests are hard to debug when they fail, integration tests hit the middle ground
- [ ] The bias explicitly acknowledges where unit tests are the right choice: isolated algorithmic logic, pure functions, parser combinators -- cases where the unit boundary is genuinely the right test boundary
- [ ] The bias explicitly acknowledges the role of e2e tests: small, curated suite covering the most common flows and critical edge cases, kept passing religiously
- [ ] The existing tradeoff framework and desiderata are not removed or contradicted -- the bias is additive
- [ ] Anti-mocking stance is strengthened: mocking should be rare (approaching never), and when used, only at coarse-grain system boundaries (external services, databases). Fakes remain the recommended alternative
- [ ] Framing avoids dogmatism -- the additions explain *why* the bias exists, not just *what* the bias is

## Open Questions
- None.

## Out of Scope
- Changing the test-driven-development skill's workflow (TDD remains test-level-agnostic)
- Prescribing specific test frameworks or tools
