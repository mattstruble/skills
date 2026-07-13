# Type-Driven Design

*Source: Alexis King, "Parse, don't validate" (2019) — `docs/sources/type-driven-design.md`.*

---

## Parse, Don't Validate

Alexis King argues that the difference between parsing and validating is
*information preservation*. A validator answers "is this valid?" and discards
the answer — the caller still holds the original unrefined value and must
re-check at every use site. A parser answers "is this valid?" and hands back
a value that *cannot be invalid*: the proof is embedded in the type.

The practical consequence: a `validate_non_empty(items) -> None` function
forces every downstream caller to re-check emptiness, because the type still
says `list`. A `parse_non_empty(items) -> NonEmpty` function eliminates those
checks — the type carries the guarantee forward.

This is a design philosophy, not a formal theorem. The slogan "parse, don't
validate" is a heuristic for choosing between two shapes of function: one that
checks and discards, and one that checks and returns.

---

## Strengthen the Argument Type

Alexis King argues that when a function requires a precondition, the right
response is to strengthen the argument type — not to weaken the return type.
The Haskell example: `head :: [a] -> Maybe a` is a partial function that
forces every caller to handle the `Nothing` case. `head :: NonEmpty a -> a`
is total — the precondition is encoded in the argument type, and the caller
handles it *once*, at the point where they construct the `NonEmpty`.

The principle generalizes: a function that accepts a raw type and re-checks
a precondition on every call is doing the caller's job. Strengthen the
argument type so the precondition is checked once, at construction, and
downstream functions receive a type that already satisfies it. In Python,
this means smart constructors (`__post_init__` or class-method factories)
rather than per-call guards — see `python-design/references/core-patterns.md`
"Refine Fields at the Boundary" for the runtime mechanics.

---

## Make Illegal States Unrepresentable

Alexis King argues that the primary goal of type-driven design is to pick
data structures that rule out bad states *by construction*. If the data
structure cannot represent the invalid state, no runtime check is needed —
the invalid state simply cannot exist.

Two canonical examples: a `dict` structurally prevents duplicate keys (a
`list[tuple]` does not); a `NonEmpty` type structurally prevents an empty
collection (a `list` does not). When you reach for a `list` and add a
"must not be empty" comment, you have chosen a type that can represent the
illegal state and deferred the enforcement to runtime checks scattered
through the codebase.

The design question is: *what data structure makes the illegal state
unrepresentable?* Choose that structure, and the checks disappear.

Python cannot enforce field-level constraints at compile time the way
Haskell's type system can. See `python-design/references/core-patterns.md`
"Refine Fields at the Boundary" for runtime enforcement via smart
constructors and the honesty caveat about what type checkers can and
cannot prove.

---

## Shotgun Parsing (Antipattern)

Shotgun parsing is the antipattern of interleaving validation code with
processing code. The program acts on partially-valid input, then must roll
back or handle errors mid-flight. The root cause is that the "parse phase"
and the "execute phase" are not separated — validation happens in the same
code that acts on the data.

The remedy is stratification: a parse phase that converts raw input into
fully-validated domain types, followed by an execute phase that operates
only on those types. Failure is confined to the parse phase; the execute
phase can assume its inputs are valid. This is the same discipline as
"validate at boundaries" (see `software-design/SKILL.md`) but adds the
information-preservation framing: the parse phase should *return* the
validated types, not just check and discard.

See `references/engineering-judgment.md` "Validate Fully at Load" for the
related frontier-of-uncertainty principle.

---

## Push the Burden of Proof Upward

Get data into its most precise representation as early as possible — ideally
at the system boundary. Alexis King's practical technique: write the
functions you wish you had (accepting fully-refined domain types), then
bridge the gap with a parser at the edge that converts raw input into those
types. The parser is the only place that handles invalid input; everything
downstream is clean.

Parsing in multiple passes is fine. You do not have to convert everything
in one step; a pipeline of refinement passes is valid. Use judgment — it is
not always achievable to parse everything upfront, and forcing it can create
awkward intermediate types. The goal is to push the boundary of uncertainty
as close to the input source as possible, not to achieve a single-pass parse
at any cost.

---

## Avoid Denormalized Data

Out-of-sync copies of the same data are a representable illegal state. If
two fields must always agree, the data structure allows them to disagree —
and they will, eventually. Prefer a single authoritative source; derive
dependent values on demand rather than storing them separately. This is
"make illegal states unrepresentable" applied to data layout: the illegal
state (two copies out of sync) disappears when there is only one copy.
