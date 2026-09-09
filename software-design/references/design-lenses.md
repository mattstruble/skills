# Design Lenses

Principles from industrial and graphic design applied to software interfaces.
These are lenses for seeing structural quality — use them to diagnose why
something feels off and to articulate what would make it better.

---

## Affordances and Signifiers

An **affordance** is a property that suggests how something should be used
(Norman, *The Design of Everyday Things*). In code: function shape, parameter
names, and type structure communicate the correct calling convention.

**Key question:** Can a caller understand correct usage from the signature
alone, without reading the body or docs?

Weak affordances force the caller to guess:

```python
# Caller must read the implementation to know what True, None, "", False, -1 mean
process(data, True, None, "", False, -1)
```

Strong affordances communicate usage through structure:

```python
# Fluent chain — each method name describes the operation
query.filter(status="active").order_by("created_at").limit(50)

# Keyword-only — caller cannot pass positional mystery arguments
def create_user(*, name: str, email: Email, role: Role) -> User: ...
```

**Red flag:** If correct usage requires reading the implementation, the
interface has weak affordances. The fix is usually keyword arguments, refined
types, or a builder pattern.

### Signifiers Make Affordances Visible

Signifiers are the cues that make affordances perceivable. Four levels, from
weakest to strongest:

1. **Names** — function names, parameter names, module names
2. **Types** — argument types, return types, type aliases
3. **Docstrings** — intent, constraints, examples
4. **Error messages** — guidance when usage is wrong

Each level reinforces the one above. Strong names reduce the need for
docstrings; strong types reduce the need for runtime errors.

### Errors as Signifiers

Error messages are signifiers for incorrect usage. They guide the caller
toward correct behavior — or they don't.

```
# Weak: caller must guess what's wrong
ValidationError: invalid value

# Strong: tells what failed, what was received, and how to fix it
ValidationError: 'email' must be a valid email address.
  Got: 'not-an-email'
  Tip: Format must be 'user@domain.tld'
```

### Observability as Signifiers

In production systems, operators are users. Structured logs, named metrics,
and correlation IDs are signifiers that guide operators navigating incidents.
A log line `Processing request` is a weak signifier. A log line
`billing.charge.started request_id=abc-123 user_id=42 amount=99.00` is
strong — every token narrows the search space.

---

## Conceptual Model

The **conceptual model** is the mental representation a user builds about how
a system works (Norman; Lakoff & Johnson, *Metaphors We Live By*).

**Key question:** If a new caller explains this API back to you after 5
minutes, what would they say? Is that accurate?

### Three-Layer Model Test

1. **Language layer** — Do labels match domain terms users already use?
   If the domain says "invoice" and the code says "billing_document," the
   model has friction.
2. **Behavior layer** — Does the system do what it looks like it will do?
   A `save()` method that sometimes doesn't persist (because it batches)
   violates the model.
3. **Feedback layer** — Does the system report what just happened? After
   calling `deploy()`, does the caller know whether it succeeded, is
   pending, or was a no-op?

### Leaky Abstraction Test

If a caller must understand the implementation to debug or correctly use
the interface, the abstraction is leaking.

```python
# Clean model: "persistent stateful connection" — caller's mental model is accurate
session = requests.Session()
session.get("https://api.example.com/users")

# Leaky model: "connection pool" where connections silently expire.
# Caller must understand internal timeout behavior to avoid stale-connection errors.
pool = ConnectionPool(max_connections=10)
conn = pool.get()  # might be stale — caller must handle reconnection
```

### Metaphor Selection

Choose metaphors from domains callers already understand:

- **Session** → web browsing (stateful, starts and ends)
- **Stream** → water (flows one direction, consumed once)
- **Queue** → waiting in line (FIFO, fair)
- **Pool** → swimming lanes (borrow one, return it when done)

When implementation violates the chosen metaphor, callers' predictions
will be wrong. A "queue" that allows priority jumping isn't a queue — it's
a priority scheduler. Name it that way.

---

## Information Scent

Pirolli & Card's **information foraging theory** (1999): users follow cues
(scent) suggesting they're getting closer to their goal. In code, scent
lives in names — file names, module names, function names, import paths.

**Key question:** Given only the names visible from outside, can a new
engineer guess where to look?

### Strong Scent Communicates Domain, Not Mechanism

```
app/payments/charge.py           # strong: domain is clear
app/handlers/payment_v2.py       # weak: mechanism + version noise
app/services/service3.py         # none: meaningless
```

### Graveyard Names

Names where scent goes to die: `utils/`, `helpers/`, `common/`, `shared/`,
`misc/`. They contain every kind of scent, so they contain none. A new
engineer looking for tax calculation logic will not think to look in
`utils/helpers.py`.

### The Renaming Test

If you had to rename a module to make a new engineer find it on their first
try, what would you call it? That's the right name.

### Import Path as Scent Trail

Every token in an import path should narrow the search:

```python
from app.billing.invoices.line_items import calculate_tax
#    ^^^      ^^^^^^^^ ^^^^^^^^^^       ^^^^^^^^^^^^^
#    app  →   billing  → invoices  →    specific function
# Each token narrows. Reader knows where they are.

from utils.helpers import calculate_tax
# Trail goes cold at 'utils'. Reader learns nothing.
```

---

## Gestalt Principles in Code

Gestalt psychology describes how humans perceive structure. These principles
apply directly to code organization:

| Gestalt Principle | Code Application |
|---|---|
| **Proximity** | Related functions and constants near each other; related tests adjacent to the code they test |
| **Similarity** | Things that look alike behave alike — consistent naming, parameter order, return conventions |
| **Common Region** | Module boundaries, class bodies, file organization signal "these things belong together" |
| **Continuity** | Control flow reads top-to-bottom without surprising jumps; avoid deeply buried early returns |
| **Figure/Ground** | Domain logic is the figure; infrastructure, error handling, logging recede into background |
| **Closure** | Consistent structure lets readers pattern-complete — if all services follow the same shape, new ones are understood faster |

**Practical implication:** Inconsistency is noise that forces conscious
attention. Every deviation from an established pattern costs the reader
cognitive effort to determine whether the deviation is meaningful or
accidental. Consistency is a cognitive load reduction strategy — it lets
readers predict structure and focus on what's actually different.

---

## Design Critique Workflow

For reviewing existing code through a design lens (separate from correctness
review):

1. **Frame:** What is this interface for? Who calls it? What is their goal?
2. **Conceptual Model Test:** Without reading the implementation, what model
   does the public interface present? Is it accurate? Simple enough?
3. **Lens Sweep:** Run each lens as a question:
   - Affordances — can the caller use this correctly from the signature?
   - Signifiers — do names, types, and errors guide toward correct usage?
   - Constraints — does the type system prevent misuse, or just docs?
   - Scent — can a new engineer find this from the outside?
   - Signal/noise — does every element carry information?
   - Negative space — what was left out, and was that a good decision?
   - Cognitive load — can a competent engineer hold this in working memory?
4. **Prioritize:** Which violations actually matter for this context? Not
   every issue is worth fixing. Name the top 1–3.
5. **Suggest:** Ground suggestions in the principle, not personal preference.
   *"This parameter adds cognitive load without enabling a use case that
   couldn't be handled by X"* beats *"I'd simplify this."*

---

## Pre-Implementation Design Process

When designing something new:

1. **Frame the problem** — What is the human need, not the technical
   requirement? Who will call this, and what are they trying to accomplish?
2. **Sketch alternatives** — Produce 2–3 rough calling conventions in
   pseudocode before writing real code. The first idea is rarely the best.
   ```python
   # Sketch A: single function with options
   charge(account, amount, currency="USD", idempotency_key=None)

   # Sketch B: builder
   Charge(account, amount).in_currency("EUR").idempotent(key).execute()

   # Sketch C: separate functions per currency model
   charge_usd(account, amount)
   charge_multi(account, amount, currency)
   ```
3. **Apply the lenses** — Which sketch has the strongest affordances?
   Cleanest conceptual model? Least cognitive load?
4. **Choose and articulate the model** — Before writing implementation,
   state: *"The mental model this API presents is ___."* If you can't state
   it simply, the design isn't ready.
5. **Implement** — The design is a hypothesis. Plan to iterate once real
   callers use it.
