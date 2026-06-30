# Engineering Judgment

Covers the judgment calls that sit between knowing the rules and applying them
well: understanding code before changing it, reasoning about runtime behavior,
calibrating optimization effort, fixing root causes, and knowing when the
rules themselves are the problem. Read this when you're about to change code
you don't fully understand, when a profile is flat and you're not sure where
to push, or when a blanket rule is pulling you toward obviously worse code.

Synthesized from Jonathan Blow stream clips (youtube.com/@JBH-p5b); per-topic sources in docs/sources/jonathan-blow.md.

---

## Document the Road Not Taken

When you record a design decision, also record the alternatives you considered
and why the simpler ones were rejected. Without that, the tradeoff knowledge
evaporates — future maintainers see the choice but not the reasoning. A
one-paragraph note in a comment or ADR is enough. This extends the skill's
"comment the why" principle: the *why* includes the paths not taken.

---

## Understand Before You Change: Software as a Web of Invariants

Real programming is changing code while preserving a large set of invariants
that keep it working. When you hit code you don't understand, stop and
understand it — skipping it ("seems fine") is self-deception that costs more
later.

**Soft-failure method (design/change-safety discipline).** When a system runs
but produces wrong output, an invariant is violated somewhere in the chain.
Enumerate everything that must be true for the output to be correct, verify
each component independently with targeted debug output, and narrow candidate
causes systematically. When the situation is very confusing, expect multiple
simultaneous faults — a single-fault assumption will mislead you. If you can
enumerate the invariants, you designed the system well enough to reason about
it; if you can't, that's the design problem.

---

## Statics vs Dynamics: Simplify When Scared

Judge code by its runtime behavior, not its line count. A few lines of calls
and an `if` can be bad code if its dynamics — what it does at runtime, in what
order, with what side effects — are hard to reason about.

Feeling "scared" of a section is a reliable signal it's too complex; there is
usually no fundamental reason it must be. When stuck on a hard bug, try
simplifying the surrounding code regardless of the bug: if that fixes it,
good; if not, the bug has flagged a section worth re-hardening anyway.

---

## Complexity Overshoots Its Optimum

Adding features creates value — for a long time. So teams keep adding. But
past some point you degrade the product as fast as you add value, hit
equilibrium, then overshoot: destroying value while believing you're creating
it. The feedback lag is months to years, so you're off course long before you
notice. Schedule deliberate stops to re-harden instead of only piling on.

---

## Optimization Judgment

Measure work-per-unit-time, not raw throughput. Frames per second mean nothing
without accounting for how much the code actually does. In mature software,
profiles are flat — many items each at 0.3–1% — so speedups mean grinding many
small contributors. If one change yields a huge win, you were probably
negligent earlier.

Know when not to optimize. A robust recompute-from-scratch that holds no extra
state often beats a stateful "optimized" version that corrupts and is hard to
debug; take the marginal CPU loss for robustness. Choose data structures by
actual access cost: red-black trees pay off only when seeks are expensive (e.g.
on disk); in RAM, simpler structures win. Profile first — the simplest approach
(read the whole file into memory, then parse) often wins over incremental
cleverness.

---

## Fix the Root Cause, Not the Symptom

Papering over a glitch — adding hysteresis, a "self-healing" retry, a
compensating adjustment — hides the real defect and adds complexity. Find and
fix what actually produces the wrong result. Workarounds compound; root fixes
don't. Jonathan Blow argues this failure mode accelerates with LLM-assisted
coding: the model patches symptoms fluently while the underlying invariant
violation remains.

---

## Match the Natural Amount of State

The ideal program is not zero-side-effect / zero-global-state. Every problem
has a *natural* amount of state; the goal is to do exactly that amount. When
the problem is inherently stateful, name the state clearly rather than hiding
it through parameter laundering or hidden closures. This calibrates the skill's
"default to immutable / pure core" guidance: that is a direction, not an
absolute.

---

## Rules Aren't Laws

Jonathan Blow argues that blanket prohibitions — "no nested ifs," "functions
must be ≤ 3 lines," "always use OOP" — are classroom dogma. You cannot write
real software under them. Named paradigms are over-credited; it's just code.
He is similarly skeptical of functional programming as commonly practiced
("largely cargo-culting"). He concedes the real failure mode exists —
pathological piles of `if`s are bad — but the rule overshoots. This reinforces
the skill's "these are lenses, not laws" note: apply principles with judgment,
not as a checklist.

---

## Make Cost Explicit at the Call Site

Favor an explicit interface so the resource cost is visible where it's paid.
If a value is pinned for the duration of a block, pass it in explicitly —
implicit pinning silently exhausts resources and hides cost from the reader.
This extends the skill's Honesty principle: hidden cost is a hidden side
effect.

---

## Validate Fully at Load

Parsing has two jobs: reading primitives, and validating contents and placing
data where it belongs. A generic format (JSON) only does the first, pushing
the "frontier of uncertainty" from load-time into the entire program — every
later access must re-check existence and handle the missing case. Validate
everything at load; afterward there is zero uncertainty about what exists and
where. Concrete techniques: default-value diffing, per-field version stamps,
deprecated fields kept while old versions load and deleted at ship. This
extends the skill's "validate at boundaries" guidance to the load path.

---

## Design for the Hard Cases

Roughly 98% of new abstractions make already-easy things marginally easier and
don't help the hard, gnarly problems — but the hard problems are the limiting
factor on what you can build. Spend design effort there. Good engineering
judgment means doing cost/benefit analysis and reaching for the simple solution
over the complex one, but not pretending the hard cases don't exist.

---

## Compactness as a Quality Signal

Jonathan Blow argues that smaller code for the same capability tends to be
better, and that bloat is what happens with many programmers and mass
contribution. Use this as a one-line reinforcement of minimalism. Note that
LOC is a weak metric; the claim is directional. The underlying point: if two
solutions solve the same problem, the more compact one is usually easier to
understand, easier to change, and has fewer places to hide bugs.
