---
name: software-design
description: Use this skill when writing code from scratch (scripts, functions, APIs, modules, classes) or restructuring existing code (refactoring bloated classes, splitting large functions, reorganizing parameters). Applies to concrete implementation tasks like "build a payment module", "write a script that processes files", "this class does too many things", "this function has 10+ parameters", or "should I use inheritance here?" (when applied to a specific class or module). Also trigger when the user wants to know whether to use inheritance vs composition for a concrete design, needs to split a large module, is designing a new service or library, or is unsure how to structure a codebase — even if they don't explicitly ask for "design help". The skill guides toward small, focused, composable design. Do NOT use for debugging existing errors, language syntax questions ("how do I use TypedDict?"), framework setup (CI/CD, database migrations), performance benchmarking, test quality criteria (see test-design), API surface conventions (see api-design), or abstract pattern theory discussions.
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
4. **Does it do what it says?** (Honesty)
5. **What happens when things go wrong?** (Thoroughness)
6. **Will this still make sense in a year?** (Longevity Over Trend)

These are lenses, not laws. They sometimes conflict -- minimalism might suggest
fewer types while thoroughness demands explicit error handling. Use judgment.
The goal is software that is genuinely useful, easy to understand, and
respectful of the humans who interact with it.

---

## References

| Reference | When to read |
|---|---|
| `references/patterns.md` | Full before/after catalog for specific refactoring patterns -- bloated config, deep inheritance, hidden side effects, immutability, declarative style, etc. Consult when you need a concrete model for a specific principle. |
