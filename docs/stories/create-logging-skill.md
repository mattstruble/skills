# Story: Create Logging Skill

## Source
Brainstorm: Grug Brain Philosophy Integration
Behaviors covered:
- Logging/observability is entirely absent from all existing skills
- Grug identifies logging as massively undervalued and under-taught
- Concrete practices: log all branches, correlation IDs, dynamic log levels, per-user debugging

## Summary
Create a new standalone, language-agnostic logging skill that covers what to log, how to structure logs, and how to make logging operationally useful. Uses pseudocode-style examples to stay concrete without coupling to any specific language or framework.

## Acceptance Criteria
- [ ] Skill triggers when writing new services, adding error handling, implementing observability, or when logging is mentioned
- [ ] Covers what to log: all conditional branches (not just the entry point), entry/exit of significant operations, error context with enough state to reproduce
- [ ] Covers correlation/request IDs for tracing requests across service boundaries
- [ ] Covers dynamic log level control: runtime-adjustable without redeployment, per-user debugging when possible
- [ ] Provides guidance on what belongs at each log level (debug, info, warn, error)
- [ ] Includes at least 2 pseudocode before/after examples showing the difference between poor and effective logging
- [ ] Communicates the cultural point: logging is undervalued in education and practice, and is worth investing in early
- [ ] SKILL.md stays under 500 lines and uses no language-specific libraries or frameworks
- [ ] Skill description follows triggering-only convention (no workflow summary)

## Open Questions
- None.

## Out of Scope
- Language-specific logging library configuration (Python `logging`, `structlog`, Java `log4j`, etc.)
- Log aggregation infrastructure (ELK, Loki, Datadog)
- Metrics and tracing (distinct from logging, though related)
