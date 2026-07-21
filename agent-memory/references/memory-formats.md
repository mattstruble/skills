# Memory Storage Formats

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## The Format Spectrum

Five formats exist on a spectrum from simple to capable. Each trades
expressiveness for complexity. The right choice depends on the volume,
criticality, and structure of the data being stored.

---

## Simple Notes

Atomic key-value pairs. Each memory is a single fact with no context.

```json
{
  "preferred_language": "English",
  "theme": "dark",
  "timezone": "America/New_York",
  "dietary_restriction": "vegetarian"
}
```

**Strengths:**
- O(1) read and write — no parsing overhead
- Easy to merge across sessions (last-write-wins per key)
- Minimal storage footprint

**Weaknesses:**
- Associations between facts are lost — the agent can't know *why* the user
  prefers dark mode or what context that preference applies to
- No disambiguation — a second value for the same key silently overwrites the first
- No history — can't tell when a fact was learned or from what source

**Best for:** High-volume, non-critical preferences where context doesn't
change the meaning of the fact. UI preferences, language settings, notification
toggles.

---

## Enhanced Notes

Full paragraphs that preserve the context in which a fact was learned.

```
The user mentioned they live in Seattle and work remotely. They prefer
morning meetings before 10am Pacific and avoid scheduling on Fridays.
They have a dog named Biscuit and mentioned allergies to shellfish during
a conversation about restaurant recommendations.
```

**Strengths:**
- Semantically complete — the agent understands the fact in context
- Natural language form is easy to generate and retrieve via semantic search
- Captures nuance that key-value pairs lose

**Weaknesses:**
- Hard to partially update — changing one fact requires rewriting the whole note
- No structured access — extracting a specific field requires parsing
- Grows large quickly; retrieval quality degrades as notes get longer

**Best for:** Biographical summaries, relationship context, one-time facts
that rarely change and benefit from narrative context.

---

## JSON Cards

Hierarchical key-value with categories. Enables partial field updates without
rewriting the whole record.

```json
{
  "identity": {
    "name": "Alex",
    "location": "Seattle, WA"
  },
  "preferences": {
    "meeting_times": "mornings before 10am Pacific",
    "avoid_days": ["Friday"],
    "dietary": "no shellfish"
  },
  "household": {
    "pets": [{"name": "Biscuit", "type": "dog"}]
  }
}
```

**Strengths:**
- Partial updates — change `preferences.dietary` without touching `identity`
- Structured access — the agent can read a specific field without parsing prose
- Categories provide natural organization

**Weaknesses:**
- Schema rigidity — new fact types require schema changes
- No disambiguation context — two values for `location` are a conflict with no resolution path
- No provenance — can't tell when or why a field was set

**Best for:** Structured user profiles where the schema is stable and partial
updates are frequent.

---

## Advanced JSON Cards

Extends JSON Cards with `backstory`, `person`, `relationship`, and `timestamp`
fields. The `backstory` field is the key addition — it records *why* a fact
was stored, enabling disambiguation.

```json
{
  "identity": {
    "name": "Alex Chen",
    "person": "primary_user",
    "relationship": "self"
  },
  "addresses": [
    {
      "type": "work_delivery",
      "value": "123 Main St, Seattle, WA 98101",
      "backstory": "User provided for work package deliveries in March 2024",
      "timestamp": "2024-03-15T10:22:00Z"
    },
    {
      "type": "personal",
      "value": "456 Oak Ave, Bellevue, WA 98004",
      "backstory": "User mentioned as home address when discussing grocery delivery",
      "timestamp": "2024-06-02T14:05:00Z"
    }
  ],
  "preferences": {
    "meeting_times": {
      "value": "mornings before 10am Pacific",
      "backstory": "Stated preference when scheduling recurring team sync",
      "timestamp": "2024-01-20T09:00:00Z"
    }
  },
  "relationships": [
    {
      "person": "Jordan",
      "relationship": "spouse",
      "backstory": "Mentioned when discussing anniversary dinner reservation"
    }
  ]
}
```

**Key fields:**

| Field | Purpose |
|---|---|
| `backstory` | Why this fact was stored; enables disambiguation |
| `person` | Who this fact is about (self, family member, colleague) |
| `relationship` | How this person relates to the primary user |
| `timestamp` | When this fact was recorded; supports recency-based conflict resolution |

**Strengths:**
- Disambiguation without conflict — two addresses can coexist when their
  backstories distinguish the context
- Provenance — the agent knows when and why each fact was stored
- Partial updates — individual fields update without touching the whole record
- Compact enough for Tier 1 (always-in-context resident facts)

**Weaknesses:**
- More verbose than simple JSON Cards
- Backstory quality depends on the quality of the extraction prompt
- Schema still requires maintenance as new fact categories emerge

**Best for:** Critical low-volume personalization data — the Tier 1 resident
structured facts that the agent needs in every session.

---

## Code (Executable Python Objects)

Bojie Li argues that representing user memory as executable Python objects
with constraint methods provides capabilities no data format can match:
deterministic aggregation, conflict detection via constraint violations, and
enforcement of invariants.

```python
class UserMemory:
    def __init__(self):
        self.name: str = ""
        self.birth_year: Optional[int] = None
        self.age: Optional[int] = None
        self.addresses: list[Address] = []
        self.preferences: dict[str, Any] = {}

    def set_age(self, age: int, source: str) -> None:
        if self.birth_year is not None:
            expected = datetime.now().year - self.birth_year
            if abs(age - expected) > 1:
                raise MemoryConflict(
                    f"Age {age} inconsistent with birth_year {self.birth_year}",
                    source=source
                )
        self.age = age

    def add_address(self, address: Address) -> None:
        # Addresses accumulate; backstory distinguishes them
        self.addresses.append(address)

    def get_current_address(self, context: str) -> Optional[Address]:
        # Return the most contextually appropriate address
        matches = [a for a in self.addresses if context in a.backstory]
        return max(matches, key=lambda a: a.timestamp) if matches else None

    def validate(self) -> list[str]:
        """Return list of constraint violations."""
        violations = []
        if self.age and self.birth_year:
            expected = datetime.now().year - self.birth_year
            if abs(self.age - expected) > 1:
                violations.append(f"age/birth_year inconsistency")
        return violations
```

**Strengths:**
- Constraint enforcement — invariants are checked at write time, not discovered at read time
- Deterministic aggregation — merging memories from multiple sessions is a method call, not a prompt
- Conflict detection — violations surface immediately with structured error messages
- Full Python expressiveness — arbitrary logic for complex memory operations

**Weaknesses:**
- Highest complexity — requires code generation, execution environment, and versioning
- Regeneration cost — the "User as Code" pattern requires periodic full regeneration
- Debugging — constraint violations in generated code are harder to diagnose than data conflicts

**Best for:** Systems where constraint enforcement is a hard requirement —
financial data, health data, or any domain where inconsistent memories have
serious consequences.

---

## Migration Patterns

Formats are not permanent. As a system matures, the right format often changes.

**Simple Notes → JSON Cards.** When you find yourself storing facts that
logically belong together (multiple addresses, multiple preferences per
category), migrate to JSON Cards. The migration is mechanical: group existing
keys into categories.

**JSON Cards → Advanced JSON Cards.** When disambiguation conflicts appear
(two values for the same field that are both correct in different contexts),
add `backstory` and `timestamp` fields. Existing records get empty backstory
fields; new writes populate them.

**Advanced JSON Cards → Code.** When constraint violations are causing data
quality problems that backstory-based disambiguation can't solve, migrate to
executable objects. This is a significant investment — only justified when
the constraint enforcement value is clear.

**Downgrade signals.** If the Code format's regeneration overhead is causing
latency problems and constraint violations are rare, downgrade to Advanced
JSON Cards. Complexity should match the actual problem, not the anticipated one.

---

## The Hybrid Recommendation

Most production systems don't choose one format — they use a hybrid:

**Tier 1 (resident, always in context):** Advanced JSON Cards. Compact enough
to include in every prompt, structured enough for partial updates and
disambiguation. The agent always has the user overview.

**Tier 2 (on-demand, retrieved as needed):** Raw conversation storage. Full
session transcripts stored verbatim, retrieved via semantic search when the
agent needs precise details. No structure imposed — the retrieval layer
handles relevance.

This combination provides the overview (Tier 1) and the details (Tier 2)
without the complexity of a full Code-based memory system. The Code format
is reserved for systems with hard constraint requirements.

**When to deviate:**
- High-volume, low-criticality facts → Simple Notes for Tier 1 (lower overhead)
- Narrative-heavy user profiles → Enhanced Notes for Tier 1 (richer context)
- Hard constraint requirements → Code for Tier 1 (enforcement over simplicity)
