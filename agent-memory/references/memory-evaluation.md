# Memory Evaluation Framework

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## The Three-Level Framework

Memory system quality is not binary. A system can store and retrieve facts
correctly (Level 1) while completely failing to provide value across sessions
(Level 3). The three-level framework makes this progression explicit and
testable.

| Level | Name | What it tests | Architecture required |
|---|---|---|---|
| 1 | Basic Recall | Single-session fact retrieval | Any storage + retrieval |
| 2 | Multi-Session Retrieval | Cross-session aggregation and disambiguation | Conflict resolution + session indexing |
| 3 | Proactive Service | Anticipatory synthesis | Two-tier architecture (Tier 1 + Tier 2) |

Most systems are tested only at Level 1. Levels 2 and 3 require deliberate
test design and, for Level 3, a specific architectural prerequisite.

---

## Level 1 — Basic Recall

**What it tests.** The agent retrieves a fact that was explicitly stored in a
single session. The user asks directly; the agent answers from memory.

**Passing criteria.** The agent returns the stored value accurately, without
hallucinating related facts or confabulating context that wasn't stored.

### Test Scenarios

**Scenario 1.1 — Direct preference recall**
- Setup: In session 1, user states "I prefer dark mode."
- Query (session 2): "What display mode do I prefer?"
- Pass: Agent returns "dark mode" without prompting the user to repeat it.
- Fail: Agent asks the user to re-state their preference, or returns a different value.

**Scenario 1.2 — Numeric fact recall**
- Setup: In session 1, user provides their account number.
- Query (session 2): "What's my account number?"
- Pass: Agent returns the exact stored value.
- Fail: Agent returns a plausible but incorrect number (hallucination), or says it doesn't know.

**Scenario 1.3 — Format-specific recall**
- Setup: In session 1, user states dietary restriction.
- Query (session 2): "Can I eat shellfish?"
- Pass: Agent correctly applies the stored restriction to answer the question.
- Fail: Agent answers generically without applying the stored fact.

**Scenario 1.4 — Negative recall (absence)**
- Setup: No dietary restriction stored.
- Query: "Do I have any dietary restrictions on file?"
- Pass: Agent correctly reports no restriction is stored.
- Fail: Agent confabulates a restriction or hedges without checking.

### What Level 1 Does Not Test

Level 1 does not test whether the agent can handle the same fact appearing in
multiple sessions, whether it can resolve contradictions, or whether it can
synthesize facts to answer questions the user didn't ask. A system that passes
Level 1 may still fail completely at providing cross-session value.

---

## Level 2 — Multi-Session Retrieval

**What it tests.** The agent gathers and reconciles information scattered
across multiple sessions, including disambiguation when the same user provides
different values in different contexts.

**Passing criteria.** The agent correctly aggregates facts from multiple
sessions, resolves contradictions using the appropriate strategy (recency,
source credibility, or contextual disambiguation), and distinguishes between
facts that appear to conflict but are actually context-dependent.

### Test Scenarios

**Scenario 2.1 — Cross-session aggregation**
- Setup: Session 1 mentions the user has a Toyota Camry. Session 3 mentions
  the user has a Honda Civic. Session 5 asks about scheduling a service appointment.
- Query (session 6): "Which car needs service?"
- Pass: Agent correctly identifies which car was mentioned in session 5 as
  needing service, without confusing it with the other vehicle.
- Fail: Agent picks the wrong car, or asks the user to re-specify.

**Scenario 2.2 — Contradiction detection**
- Setup: Session 1 stores home address as "123 Main St." Session 4 stores
  home address as "456 Oak Ave."
- Query (session 7): "What's my home address?"
- Pass: Agent surfaces both values with their context, or applies recency
  priority and returns the session 4 value with a note that it was updated.
- Fail: Agent silently returns one value with no indication of the conflict,
  or returns the wrong value.

**Scenario 2.3 — Contextual disambiguation**
- Setup: Session 2 stores "work delivery address: 123 Main St." Session 5
  stores "home address: 456 Oak Ave."
- Query (session 8): "Where should I send the work package?"
- Pass: Agent returns the work delivery address, not the home address.
- Fail: Agent returns the wrong address or asks the user to re-specify.

**Scenario 2.4 — Temporal fact evolution**
- Setup: Session 1 stores "current project: mobile app." Session 6 stores
  "current project: data pipeline."
- Query (session 9): "What am I working on?"
- Pass: Agent returns the session 6 value (most recent), not the session 1 value.
- Fail: Agent returns the stale value or both values without priority.

**Scenario 2.5 — Person disambiguation**
- Setup: Multiple sessions mention different people named "Alex" — the user's
  colleague and the user's sibling.
- Query: "What did I say about Alex's schedule?"
- Pass: Agent asks for clarification, or correctly identifies which Alex based
  on context.
- Fail: Agent conflates the two people or returns facts about the wrong one.

### What Level 2 Does Not Test

Level 2 tests reactive retrieval — the agent answers questions the user asks.
It does not test whether the agent can surface information the user didn't
ask for but would benefit from knowing.

---

## Level 3 — Proactive Service

**What it tests.** The agent synthesizes memories to anticipate needs the
user hasn't expressed. The agent surfaces relevant information without being
asked.

**Passing criteria.** The agent identifies connections between stored facts
that imply an action or alert the user would want, and surfaces that
connection at the appropriate moment — not on every interaction, and not
never.

### Architectural Prerequisite

Level 3 requires the two-tier architecture. Tier 1 (resident structured facts)
provides the overview that enables synthesis — the agent always knows the
user's upcoming trips, expiring documents, and active projects. Tier 2
(on-demand retrieval) provides the precise details when synthesis identifies
a relevant connection.

A system with only Tier 2 (raw retrieval) cannot reliably achieve Level 3
because it lacks the always-available overview. A system with only Tier 1
(structured facts) cannot achieve Level 3 because it lacks the precise
details needed to confirm and contextualize the connection.

### Test Scenarios

**Scenario 3.1 — Document expiry alert**
- Setup: Tier 1 contains passport expiry date (June 2025). Tier 1 contains
  upcoming trip to Tokyo (August 2025).
- Trigger: User asks about packing for the Tokyo trip.
- Pass: Agent proactively notes that the passport expires before the trip
  date, without being asked about passport validity.
- Fail: Agent answers only the packing question and misses the expiry conflict.

**Scenario 3.2 — Preference-based anticipation**
- Setup: Tier 1 contains dietary restriction (no shellfish). User is planning
  a dinner at a restaurant the agent helped research.
- Trigger: User asks for the restaurant's address.
- Pass: Agent provides the address and notes that the restaurant's menu
  includes shellfish dishes, flagging the relevant restriction.
- Fail: Agent provides only the address with no proactive context.

**Scenario 3.3 — Cross-domain synthesis**
- Setup: Tier 1 contains recurring medication (taken with food, twice daily).
  User mentions a fasting period for a medical procedure.
- Trigger: User asks about preparing for the procedure.
- Pass: Agent notes the medication schedule may need adjustment during the
  fasting period and suggests consulting the prescribing doctor.
- Fail: Agent provides generic preparation information without connecting the
  medication fact.

**Scenario 3.4 — Timing-based proactive alert**
- Setup: Tier 1 contains subscription renewal date (next week). User is
  discussing budget planning.
- Trigger: User asks for help categorizing monthly expenses.
- Pass: Agent includes the upcoming renewal in the expense summary without
  being asked.
- Fail: Agent omits the renewal from the expense summary.

**Scenario 3.5 — Proactive silence (negative case)**
- Setup: Tier 1 contains many facts. User asks a simple question unrelated
  to any stored fact.
- Pass: Agent answers the question without injecting irrelevant memory context.
- Fail: Agent surfaces unrelated memories, creating noise.

### Rubric for Level 3

Level 3 is harder to score than Levels 1 and 2 because proactive service
involves judgment about relevance. A useful rubric:

| Dimension | Pass | Fail |
|---|---|---|
| **Relevance** | Surfaced connection is genuinely useful to the user | Connection is tangential or irrelevant |
| **Timing** | Alert appears at a moment when the user can act on it | Alert appears too early, too late, or repeatedly |
| **Precision** | Alert cites specific stored facts | Alert is vague or hedged |
| **Silence** | Agent does not surface irrelevant memories | Agent injects memory context into unrelated interactions |

---

## Implementation References

**Mem0** and **Memobase** are open-source frameworks that implement
extract-compare-decide pipelines for memory management. Both provide
reference implementations of the conflict resolution patterns described in
§2 of the main skill. They are useful as implementation starting points,
not as architectural constraints — the three-level framework applies
regardless of which framework (if any) is used.

The key insight from both frameworks: making memory operations explicit
(ADD/UPDATE/DELETE/NOOP) rather than implicit in storage logic is what
enables Level 2 disambiguation. Systems that silently overwrite or silently
accumulate cannot reliably pass Level 2 tests.

---

## Evaluation Strategy

**Start at Level 1.** Build a test suite of direct recall scenarios before
testing higher levels. A system that fails Level 1 cannot pass Level 2 or 3.

**Level 2 requires multi-session test fixtures.** Create test datasets with
pre-populated session histories that contain known contradictions and
cross-session facts. Don't rely on live sessions for Level 2 testing — the
contradictions need to be controlled.

**Level 3 requires scenario-based evaluation.** Automated scoring is
insufficient for Level 3 — the relevance and timing dimensions require human
judgment. Use a small set of high-quality scenarios with human evaluators
rather than a large set of automated checks.

**Regression at lower levels.** Changes to conflict resolution (§2) or
consolidation (§3) can regress Level 1 recall. Run the full Level 1 suite
after any change to memory write or consolidation logic.
