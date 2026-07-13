# Type-Driven Design — Source Attribution

Provenance for skill content synthesized from Alexis King's blog post "Parse,
don't validate" (2019) and the ArjanCodes video "Stop Checking for None
Everywhere". This file is **not** registered in any skill's References table
and is never auto-loaded by an agent — it exists purely for human
traceability. The blog post was paraphrased (light quotes only); the video was
paraphrased from auto-generated captions (no verbatim quotes). Contestable
opinions are presented in the skills as the authors' stances: Alexis King on
the parse/validate philosophy; ArjanCodes on preferring exceptions over Result
types in Python.

Each section lists the source(s) that informed a skill's type-driven-design
material.

## software-design → `references/type-driven-design.md`

- Alexis King, "Parse, don't validate" (2019) — <https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/>
  *(primary — information preservation, make illegal states unrepresentable, strengthen argument types, shotgun parsing antipattern, push the burden of proof upward, avoid denormalized data)*
- ArjanCodes, "Stop Checking for None Everywhere" — <https://www.youtube.com/watch?v=h8ZwhU3PpVw>
  *(reinforces — Python mechanics of refining to a domain type at the boundary)*

## python-design → `references/core-patterns.md` ("Refine Fields at the Boundary") + `SKILL.md` ("Validation Boundaries", "Avoiding None in Domain Logic")

- ArjanCodes, "Stop Checking for None Everywhere" — <https://www.youtube.com/watch?v=h8ZwhU3PpVw>
  *(primary — raise instead of returning None, model states as distinct classes, Null Object, Sentinel, exceptions-over-Result in Python)*
- Alexis King, "Parse, don't validate" (2019) — <https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/>
  *(principle — smart constructors as parsers, downstream code holds a type that cannot be invalid)*

## api-design → `SKILL.md` (Review Checklist cross-reference)

- Alexis King, "Parse, don't validate" (2019) — <https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/>
  *(principle only — cross-reference: "when the API accepts raw input, does conversion raise on invalid data rather than silently accepting it?")*
