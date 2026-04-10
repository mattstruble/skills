---
name: application-architecture
description: Application-level structural patterns -- layering, business logic organization, data access strategy, domain modeling, and cross-boundary communication. Use when designing a new service, choosing how to structure an application, or reviewing code for architectural smells (logic in controllers, no domain boundary, tangled data access). NOT for code-level design (see software-design), API surface conventions (see api-design), or infrastructure/deployment architecture.
---

# Application Architecture

**Default to the simplest structure that works. Add architectural patterns only
when complexity demands them -- not before.**

Every decision tree below starts with a YAGNI gate. If the gate tells you to
stop, stop. Patterns exist to manage complexity; applying them to simple systems
creates the complexity they were designed to solve.

Read the relevant reference file when you need deeper trade-off analysis,
criteria, and pseudocode examples.

---

## Architectural Smell Table

When reviewing existing code, use this table to identify which decision point is
relevant. A smell is not always a problem -- check the YAGNI gate before
recommending changes.

| Smell | Likely Problem | Decision Point |
|---|---|---|
| Business logic in controllers/route handlers | Missing domain layer | Business Logic Structure |
| God service that reads, writes, validates, and transforms | Transaction Script outgrowing its context | Business Logic Structure |
| Domain objects know how to save themselves | Active Record in a complex domain | Data Access Strategy |
| Database queries scattered across business logic | No data access boundary | Data Access Strategy |
| Raw primitives everywhere (strings for money, ints for dates) | Missing Value Objects | Domain Modeling |
| Null checks throughout the codebase | Missing Special Case objects | Domain Modeling |
| Internal service calls mirror the database schema | No translation at boundary | Cross-Boundary Communication |
| Downstream changes break upstream code | Missing anti-corruption layer | Cross-Boundary Communication |
| Cascading side effects on every write | Implicit coupling through state mutation | State Changes & Side Effects |
| Audit trail bolted on after the fact | Missing event-driven state tracking | State Changes & Side Effects |

---

## 1. Business Logic Structure

**The question**: Where does business logic live, and how is it organized?

### YAGNI Gate

Simple CRUD service with <5 business rules and minimal conditional logic? ->
**Transaction Script** (procedural functions, one per operation). Stop here. No
domain model, no service layer. Add structure when the transaction scripts start
duplicating logic or growing beyond what one developer can hold in their head.

### Decision Criteria

| Choose | When | Watch for |
|---|---|---|
| **Transaction Script** | Simple operations, few business rules, logic fits in one function per use case | Duplication across scripts signals time to extract a Domain Model |
| **Domain Model** | Complex business rules, multiple entities interacting, rules that change independently | Over-modeling simple CRUD; building an object graph when a function would do |
| **Service Layer** | Multiple entry points (API, CLI, queue) need the same operations; transaction coordination needed | Anemic domain: service does all work while domain model is just a data bag |
| **Hexagonal Architecture** | Domain logic must be tested independently of infrastructure; multiple adapters swap in/out | Premature port/adapter abstraction when you have one adapter and no plans for more |

**Progression**: Most applications start as Transaction Script. When scripts
duplicate logic or conditionals multiply, extract a Domain Model. When multiple
interfaces need the same operations, add a Service Layer. When infrastructure
coupling becomes painful, consider Hexagonal Architecture.

*Implementation: See `software-design` for composition and interface design.
See `python-design` for Protocol-based port definitions.*

-> Read `references/business-logic-structure.md` for detailed trade-offs and
pseudocode.

---

## 2. Data Access Strategy

**The question**: How does the application read and write persistent data?

### YAGNI Gate

Using an ORM with straightforward queries against <10 tables? -> Use the ORM
directly. No Repository, no Gateway abstraction. The ORM *is* your data access
layer. Add abstractions when you need to test domain logic without a database, or
when query logic starts duplicating across the codebase.

### Decision Criteria

| Choose | When | Watch for |
|---|---|---|
| **Direct ORM / Query Builder** | Simple data access, schema maps closely to domain, few complex queries | Spreading query logic across business code |
| **Active Record** | Domain objects map 1:1 to database rows, limited business logic per entity | Domain complexity growing beyond what the record pattern supports |
| **Repository** | Complex domain model, need to test in isolation, query logic duplicating | Repository becoming a thin pass-through that adds indirection without value |
| **Data Mapper** | Domain schema diverges from database schema, need full decoupling | Over-engineering when schemas match; most ORMs already are Data Mappers |
| **Gateway** | Wrapping access to a specific external resource (API, file system, message queue) | Building a Gateway for a dependency you'll never swap |
| **Table Data Gateway** | Reporting queries, bulk operations, set-based logic that doesn't map to domain objects | Mixing procedural table access with OO domain access inconsistently |

**Key distinction**: Repository abstracts *collections of domain objects*.
Gateway abstracts *access to a specific resource*. A Repository contains domain
logic (query specifications, consistency rules); a Gateway is a thin wrapper
over an external system.

*Implementation: See `python-design` for Protocol-based repository interfaces.
See `api-design` for Gateway API surface design.*

-> Read `references/data-access-strategy.md` for detailed trade-offs and
pseudocode.

---

## 3. Domain Modeling

**The question**: How should domain concepts be represented in code?

### YAGNI Gate

All data is flat, with no invariants to enforce and no behavior beyond CRUD? ->
Use plain data structures (structs, dicts, dataclasses). No Value Objects, no
Aggregates. Domain modeling adds value when there are business rules that data
structures alone can't enforce.

### Decision Criteria

| Concept | Use when | Key property |
|---|---|---|
| **Value Object** | Concept defined by its attributes, not its identity (Money, DateRange, EmailAddress) | Immutable, equality by value, self-validating |
| **Entity** | Concept with a lifecycle and identity that persists across state changes (User, Order) | Mutable state, equality by identity (ID), encapsulates business rules |
| **Aggregate** | Cluster of entities/value objects with a consistency boundary -- changes go through the root | Transactional consistency: invariants hold after every operation on the root |
| **Special Case** | Specific subtype that eliminates null checks (NullCustomer, MissingOrder) | Polymorphic with the normal case; callers don't branch on null |

**Aggregate boundaries**: The most common mistake is making aggregates too large.
An Aggregate is a *transactional consistency boundary*, not a containment
hierarchy. Ask: "What data must be consistent within a single transaction?"
That's your aggregate. Everything else references by ID, not by direct object
reference.

*Implementation: See `python-design` for frozen dataclass (Value Object),
Protocol (entity interfaces), and Enum (Special Case) patterns.*

-> Read `references/domain-modeling.md` for detailed trade-offs and pseudocode.

---

## 4. Cross-Boundary Communication

**The question**: How does data cross process, service, or team boundaries?

### YAGNI Gate

Single-process monolith where all code is in the same deployment? -> Call
functions directly. No DTOs, no facades, no anti-corruption layers. These
patterns solve problems that arise from distribution, not from complexity.

### Decision Criteria

| Choose | When | Watch for |
|---|---|---|
| **DTO** | Data crosses a process/network boundary and the internal model shouldn't leak | DTOs that mirror internal models 1:1 -- if they're identical, you don't need a separate type |
| **Remote Facade** | Fine-grained internal API needs a coarse-grained external interface to reduce network calls | Facade becoming a God object that orchestrates too much; logic should stay in the domain |
| **Anti-Corruption Layer** | Integrating with an external system whose model doesn't match yours | Building an ACL for a system you control -- fix the source instead |

**DTO direction**: DTOs serve the *consumer*, not the producer. Design them
around what the caller needs, not what the database returns. A DTO that mirrors
your ORM model is not a DTO -- it's a leak.

*Implementation: See `api-design` for field naming, pagination, and error
handling in DTOs. See `software-design` for Separated Interface patterns at
boundaries.*

-> Read `references/cross-boundary-communication.md` for detailed trade-offs
and pseudocode.

---

## 5. State Changes and Side Effects

**The question**: How should the system handle writes, side effects, and derived
actions?

### YAGNI Gate

Simple request-response where each write hits one table and triggers no
downstream effects? -> Let your ORM handle transactions directly. No events, no
CQRS, no event sourcing. These patterns exist for systems where a single write
triggers multiple independent reactions or where the read model diverges from the
write model.

### Decision Criteria

| Choose | When | Watch for |
|---|---|---|
| **Unit of Work** | Multiple changes must commit or fail atomically; tracking dirty objects | Most ORMs implement this already -- don't reimplement what your framework provides |
| **Domain Events** | State change should trigger independent side effects (email, cache, notify downstream) | Events used for synchronous in-process calls that should just be function calls |
| **CQRS** | Read and write models have fundamentally different shapes or performance requirements | Applying CQRS when reads and writes use the same model -- adds two models and sync complexity for no benefit |
| **Event Sourcing** | Complete audit trail required, need to reconstruct state at any point, or domain fits naturally as event sequence | Enormous complexity cost; only justified when the event log *is* the domain model |

**Escalation ladder**: Direct ORM transactions -> Unit of Work (if ORM doesn't
cover it) -> Domain Events (when side effects appear) -> CQRS (when read/write
models diverge) -> Event Sourcing (when event log is source of truth). Each step
adds significant complexity. Justify every escalation.

*Implementation: See `software-design` for pure functions (keeping side effects
at boundaries). See `test-design` for testing event-driven architectures.*

-> Read `references/state-changes-side-effects.md` for detailed trade-offs and
pseudocode.

---

## References

| Reference | When to read |
|---|---|
| `references/business-logic-structure.md` | Choosing between Transaction Script, Domain Model, Service Layer, and Hexagonal Architecture. Detailed criteria, trade-offs, and pseudocode. |
| `references/data-access-strategy.md` | Choosing between direct ORM, Active Record, Repository, Data Mapper, and Gateway. When abstractions help vs. when they add indirection. |
| `references/domain-modeling.md` | Designing Value Objects, Entities, Aggregates, and Special Case objects. Aggregate boundary rules and common mistakes. |
| `references/cross-boundary-communication.md` | DTOs, Remote Facade, and Anti-Corruption Layer. How data should cross service and process boundaries. |
| `references/state-changes-side-effects.md` | Unit of Work, Domain Events, CQRS, and Event Sourcing. When to escalate from simple transactions to event-driven patterns. |
