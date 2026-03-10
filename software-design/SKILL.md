---
name: software-design
description: Use this skill when writing code from scratch (scripts, functions, APIs, modules, classes) or restructuring existing code (refactoring bloated classes, splitting large functions, reorganizing parameters). Applies to concrete implementation tasks like "build a payment module", "write a script that processes files", "this class does too many things", "this function has 10+ parameters", or "should I use inheritance here?". The skill guides toward small, focused, composable design. Do NOT use for debugging existing errors, language syntax questions ("how do I use TypedDict?"), framework setup (CI/CD, database migrations), performance benchmarking, or abstract pattern theory discussions.
---

# Software Design Principles

These principles guide all code writing, review, and architectural decisions.
They synthesize three traditions -- industrial design minimalism (Dieter Rams),
interface-focused OO design (ISP), and functional programming -- into a
cohesive approach to building software that is purposeful, composable, and
honest.

The underlying thread: **favor small, focused, composable pieces that each do
one thing well.** This applies at every level -- functions, modules, APIs,
systems.

---

## Purpose and Usefulness

Every piece of code exists to serve someone -- a caller, a user, a future
maintainer. Before writing anything, be clear about who it serves and what
problem it solves.

- Write code that earns its place. If a function, class, or module doesn't
  serve a clear need, it shouldn't exist yet. Resist speculative abstractions.
- Emphasize usefulness over cleverness. A straightforward solution that's easy
  to call and easy to understand beats an elegant one that requires a tutorial.
- Design from the caller's perspective. What does the consumer actually need?
  Start there, then build inward. Don't expose internal complexity through the
  interface.

## Minimalism

"Less, but better." Every line, parameter, abstraction, and dependency should
earn its keep.

- Prefer the smallest interface that serves the caller. Extra methods,
  parameters, and options create surface area for confusion and bugs. You can
  always add later; removing is painful.
- Strip non-essential features, options, and configuration. When in doubt,
  leave it out. The cost of an unused abstraction is paid by every reader who
  has to understand it.
- Avoid premature generalization. Solve the concrete problem first. Extract
  patterns only when repetition proves they're real, not when you imagine they
  might be.

## Focused Interfaces

Clients should never be forced to depend on things they don't use. This is the
Interface Segregation Principle, and it applies far beyond class hierarchies --
it's a way of thinking about every boundary in your code.

- Split broad interfaces into focused ones. A function that takes 8 parameters
  is probably doing too many things. A module that exports 30 symbols probably
  has multiple responsibilities hiding inside it.
- When an interface feels bloated, ask: "Which callers use which parts?" If
  different callers use different subsets, that's a signal to split.
- Apply this to function signatures, module exports, API endpoints, config
  objects, and data structures -- not just class interfaces.

**Example -- config bloat:**
```
# Before: one config object forces every consumer to know about everything
def process(config):  # config has 12 fields, this function uses 3
    ...

# After: accept only what you need
def process(input_path, output_format, verbose=False):
    ...
```

## Composition and Pure Functions

Build systems by composing small, focused pieces rather than extending large
ones. This is where functional programming and good OO design converge.

### Prefer Pure Functions

A pure function takes inputs, returns outputs, and does nothing else. No
hidden state, no surprise side effects, no reading from global variables.

- Pure functions are inherently testable -- pass in values, assert on the
  result. No mocking, no setup, no teardown.
- Pure functions are composable -- the output of one feeds directly into
  another.
- When a function needs to do IO or mutate state, isolate that at the
  boundary. Keep the core logic pure and push side effects to the edges.

### Immutability by Default

Mutable state is the primary source of bugs that are hard to reproduce and
hard to reason about. Treat data as values that flow through transformations
rather than containers that get modified in place.

- Default to immutable data structures. Use mutation only when performance
  requires it, and contain it to a small scope.
- Avoid long-lived mutable state. When state is necessary, make ownership and
  lifecycle explicit.
- Prefer returning new values over modifying existing ones. `sorted(items)`
  over `items.sort()` when the caller doesn't expect mutation.

### Compose, Don't Inherit

Build behavior by combining small pieces rather than layering through
inheritance hierarchies.

- Favor function composition and delegation over class inheritance. Inheritance
  couples parent and child tightly and makes the codebase brittle to change.
- When you need shared behavior, extract it into standalone functions or small
  composable units (mixins, decorators, higher-order functions) rather than
  building deep hierarchies.
- Pipelines of transformations are often clearer than inheritance chains.
  `data |> validate |> transform |> persist` tells you exactly what happens
  and in what order.

### Declarative Over Imperative

Express *what* should happen rather than *how* it should happen, when the
language and context support it.

- Prefer `map`, `filter`, `reduce` and comprehensions over manual loops when
  the intent is a data transformation.
- Declarative code communicates intent; imperative code communicates mechanism.
  Both have their place, but default to intent.

## Self-Explanatory Design

Code should communicate its purpose without requiring external explanation.

- Choose names that reveal intent. A reader should understand what a function
  does, what a variable holds, and why a module exists from the names alone.
- Structure code so the reader discovers information in the order they need it.
  Public API at the top, implementation details below. High-level flow before
  low-level mechanics.
- Use types as documentation. A well-typed function signature often makes
  docstrings about parameter types redundant.
- When something *isn't* obvious -- a non-obvious performance optimization, a
  workaround for a library bug, a subtle invariant -- that's when comments
  earn their keep. Don't comment the "what" (the code says that); comment the
  "why."

## Honesty

Code should not promise more than it delivers.

- APIs should do what their names suggest -- no hidden side effects, no
  surprising behaviors, no silent failures. A function called `get_user`
  should get a user, not also update a cache and log an analytics event.
- Error handling should be explicit. Make failure modes visible in the type
  system or API contract. Don't swallow errors or return ambiguous sentinels.
- Complexity should be visible, not hidden. If an operation is expensive, the
  API should make that clear, not disguise an O(n^2) operation behind a
  property accessor.

## Thoroughness

Care about the details. Sloppy handling of edge cases, error paths, and
boundary conditions is a form of disrespect toward users and future
maintainers.

- Handle edge cases explicitly. An empty list, a missing key, a network
  timeout -- these aren't exceptional, they're expected. Design for them.
- Validate at boundaries. Trust nothing that crosses a system boundary (user
  input, API responses, file contents). Validate early, fail clearly.
- Resource cleanup matters. Open files, connections, locks -- make sure they're
  released. Use language-appropriate patterns (context managers, defer, RAII,
  try-with-resources).

## Longevity Over Trend

Favor stable, well-understood approaches over fashionable ones.

- Choose boring technology for core infrastructure. The newest framework is
  exciting; the proven one ships products.
- Depend on abstractions, not implementations. When you must depend on
  something external, wrap it so you can swap it out. The wrapper is a form of
  honesty about what you actually need.
- Write code for the reader who comes after you. Optimize for understanding,
  not for impressing. The most maintainable code is the code that doesn't
  require the original author to explain it.

## Applying These Principles

These principles are lenses, not laws. They sometimes conflict -- minimalism
might suggest fewer types while thoroughness demands more explicit error
handling. Use judgment. The goal is software that is genuinely useful, easy to
understand, and respectful of the humans who interact with it.

When reviewing code or making design decisions, ask:

1. **Does this earn its place?** (Purpose, Minimalism)
2. **Is each piece focused on one thing?** (Focused Interfaces)
3. **Can I understand this without running it in my head?** (Purity,
   Self-Explanatory Design)
4. **Does it do what it says?** (Honesty)
5. **What happens when things go wrong?** (Thoroughness)
6. **Will this still make sense in a year?** (Longevity)
