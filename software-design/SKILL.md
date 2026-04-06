---
name: software-design
description: Use this skill when writing code from scratch (scripts, functions, APIs, modules, classes) or restructuring existing code (refactoring bloated classes, splitting large functions, reorganizing parameters). Applies to concrete implementation tasks like "build a payment module", "write a script that processes files", "this class does too many things", "this function has 10+ parameters", or "should I use inheritance here?" (when applied to a specific class or module). Also trigger when the user wants to know whether to use inheritance vs composition for a concrete design, needs to split a large module, is designing a new service or library, is unsure how to structure a codebase, wants to know when to extract a helper vs keep it inline, or is deciding whether to remove existing code (dead code, legacy logic, retry blocks) — even if they don't explicitly ask for "design help". The skill guides toward small, focused, composable design. Do NOT use for debugging existing errors, language syntax questions ("how do I use TypedDict?"), framework setup (CI/CD, database migrations), performance benchmarking, test quality criteria (see test-design), API surface conventions (see api-design), or abstract pattern theory discussions.
---

# Software Design Principles

**Favor small, focused, composable pieces that each do one thing well.** This
applies at every level -- functions, modules, APIs, systems.

See `references/patterns.md` for the full before/after catalog when you need a
concrete refactoring model for a specific pattern (bloated config, deep
inheritance, hidden side effects, etc.).

---

## Start Minimal

Every piece of code exists to serve someone -- a caller, a user, a future
maintainer. Write code that earns its place. If a function, class, or module
doesn't serve a clear need, it shouldn't exist yet. Resist speculative
abstractions.

Design from the caller's perspective: what does the consumer actually need?
Prefer the smallest interface that serves the caller -- you can always add
later, but removing is painful. When an interface feels bloated, ask: "Which
callers use which parts?" If different callers use different subsets, that's a
signal to split.

```
# Before: speculative abstraction nobody asked for
class DataPipelineOrchestrator:
    def __init__(self, source_adapter, sink_adapter, transformer_chain,
                 retry_policy, metrics_collector, feature_flags): ...
    def execute_with_hooks(self, pre_hooks=None, post_hooks=None): ...
    def execute_async(self): ...
    def execute_dry_run(self): ...

# After: solve the actual problem first
def process_records(records):
    """Filter and transform records. Extend when the need is real."""
    return [transform(r) for r in records if is_valid(r)]
```

**Chesterton's Fence**: Existing code already earned its place once -- before
removing it, understand *why* it exists. What invariant does it protect? What
edge case does it handle? What broke before it was added? Deleting code you
don't understand is how you reintroduce bugs that were already fixed. Code that
is demonstrably unreachable or has no callers can be removed without this
investigation -- the evidence of disuse is itself the answer.

**Let cut points emerge**: Don't factor too early. Wait for natural factoring
boundaries to reveal themselves through experience. The right abstraction
announces itself: a narrow interface that hides genuine complexity, a pattern
that repeats in three genuinely similar places, a boundary where two things
change at different rates. Premature extraction creates abstractions that fit
the first two cases but fight the third.

**Layered interfaces**: Design for the 80% use case first; make the 20%
possible without making the 80% harder. A simple API for simple cases, with
the full API available when needed. Don't force every caller to supply
parameters they don't care about just because one caller does.

```
# Before: every caller must handle the full complexity
def send_report(data, format, recipients, cc=None, subject=None,
                template=None, retry_count=3, timeout=30): ...

# After: compose small pieces — simple callers use the composed version,
# power users use the building blocks directly
def build_report(data, format="pdf", template=None): ...
def deliver(report, recipients, cc=None, subject=None,
            retry_count=3, timeout=30): ...

def send_report(data, recipients, format="pdf"):
    """Simple API: covers 80% of callers."""
    report = build_report(data, format)
    deliver(report, recipients)
```

---

## Compose Small Pieces

Build systems by composing small, focused pieces rather than extending large
ones.

- **Pure functions**: take inputs, return outputs, do nothing else. Inherently
  testable and composable. When a function needs IO or state mutation, push
  that to the boundary -- keep core logic pure.
- **Immutability**: default to immutable data. Mutable state is the primary
  source of hard-to-reproduce bugs. Prefer returning new values over modifying
  existing ones.
- **Composition over inheritance**: favor delegation over class hierarchies.
  Inheritance couples tightly and resists change. Pipelines
  (`validate -> transform -> persist`) are often clearer than inheritance
  chains.
- **Declarative over imperative**: express *what* should happen, not *how*.
  Comprehensions and map/filter communicate intent. But when they become hard
  to read, a named loop is clearer -- don't force it.

```
# Before: logic tangled with side effects — hard to test, hard to reuse
def calculate_discount(user_id):
    user = db.get_user(user_id)          # side effect: DB read
    discount = user.loyalty_years * 0.05
    logger.info(f"Discount: {discount}")  # side effect: logging
    analytics.track("discount_calc")      # side effect: network
    return discount

# After: pure core, side effects at the boundary
def calculate_discount(loyalty_years):
    return min(loyalty_years * 0.05, 0.30)

# Caller handles IO and side effects:
user = db.get_user(user_id)
discount = calculate_discount(user.loyalty_years)
logger.info(f"Discount: {discount}")
analytics.track("discount_calc")
```

---

## Be Honest and Thorough

Code should communicate its purpose and not promise more than it delivers.

- **Self-explanatory**: choose names that reveal intent. Comment the "why," not
  the "what." Use types as documentation. Structure code so readers discover
  things in the order they need them.
- **Honest**: APIs should do what their names suggest -- no hidden side effects,
  no silent failures. A function called `get_user` should get a user, not also
  update a cache. Make failure modes visible.
- **Thorough**: handle edge cases explicitly -- empty lists, missing keys,
  timeouts are expected, not exceptional. Validate at boundaries. Clean up
  resources.
- **Longevity**: choose boring technology. Depend on abstractions, not
  implementations. Wrap external dependencies so you can swap them. Write for
  the reader who comes after you.

**Locality of Behavior**: The behavior of a code unit should be obvious by
looking only at that unit. When you have to chase through five files to
understand what a single function does, the behavior has been spread too thin.
This complements honesty (don't hide what you do) but addresses *structural
proximity*: don't spread a single behavior across distant files when it can
live together. Co-locate the things that change together.

**Expression complexity**: Break complex conditionals into named intermediate
variables. This makes the logic readable and makes the intermediate values
inspectable in a debugger.

```
# Before: dense conditional — hard to read, hard to debug
if user.subscription_tier in ("pro", "enterprise") and not user.payment_overdue \
        and (user.trial_days_remaining > 0 or user.has_paid_invoice):
    grant_access()

# After: named intermediates — each step is readable and debuggable
is_paid_tier = user.subscription_tier in ("pro", "enterprise")
is_account_current = not user.payment_overdue
has_valid_access = user.trial_days_remaining > 0 or user.has_paid_invoice
if is_paid_tier and is_account_current and has_valid_access:
    grant_access()
```

```
# Before: name hides side effects; failure is silent
def get_user(user_id):
    user = db.query(user_id)
    cache.set(user_id, user)         # hidden side effect
    analytics.track("user_fetched")  # hidden side effect
    if not user:
        return None                  # silent failure
    return user

# After: name matches behavior; failure is explicit
def get_user(user_id) -> User:
    user = db.query(user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return user

# Caller owns the side effects:
user = get_user(user_id)
cache.set(user_id, user)
```

---

## Decision Checklist

When reviewing code or making design decisions:

1. **Does this earn its place?** (Purpose and Usefulness, Minimalism)
2. **Is each piece focused on one thing?** (Focused Interfaces)
3. **Can I understand this without running it in my head?** (Pure Functions, Self-Explanatory Design)
4. **Does it do what it says?** (Honesty, Locality of Behavior)
5. **What happens when things go wrong?** (Thoroughness)
6. **Will this still make sense in a year?** (Longevity Over Trend)
7. **Before I delete this -- do I know why it exists?** (Chesterton's Fence)
8. **Am I factoring too early, or has the pattern proven itself?** (Let cut points emerge)
9. **Is the common case simple, and the complex case possible?** (Layered interfaces)

These are lenses, not laws. They sometimes conflict -- minimalism might suggest
fewer types while thoroughness demands explicit error handling. Use judgment.
The goal is software that is genuinely useful, easy to understand, and
respectful of the humans who interact with it.

---

## References

| Reference | When to read |
|---|---|
| `references/patterns.md` | Full before/after catalog for specific refactoring patterns -- bloated config, deep inheritance, hidden side effects, immutability, declarative style, etc. Consult when you need a concrete model for a specific principle. |
