---
name: "technical-writing"
summary: "Write and revise technical documents that capable readers can scan and trust"
type: "technique"
description: "You MUST use this skill when writing, revising, or reviewing long-form technical writing for a reader: reference and onboarding docs, READMEs, runbooks, design docs, RFCs, specs, PRDs, and technical articles. Also trigger when rewriting AI-generated prose, improving readability, or when the user says 'doc rewrite' or 'make this readable'. NOT for commit messages (see git-commit), PR descriptions (see git-pr), chat or issue comments, or code comments and docstrings (see software-design)."
metadata:
  route-prompt: "technical*writing technical*doc design*doc rfc runbook runbooks readme onboarding*doc onboarding*guide reference*page doc*rewrite rewrite*doc readability blog*post article"
---

# Technical Writing

Write documents that capable engineers can scan quickly and read comfortably. The reader needs to know what this thing is, how to use it or why it was decided, and what to watch out for.

## Principles

**Informational, not promotional.** State what things do, not why they're exciting. If the reader is here, they already chose to learn this.

**Write for capable readers.** Assume the reader knows adjacent systems. Define the terms specific to this document, not the field.

**Orient fast, then mechanics.** 2-3 sentences of what this system is and how it fits. Then setup and usage. Exception: pure reference sections (flag tables, config field lists) can skip the preamble.

**Problem-first when explaining why.** State the problem before the solution when context is needed for a workaround, design choice, or constraint.

**Conversational register, no filler.** "Conversational" means direct sentence structure and natural phrasing, not casual filler phrases. Use "you" naturally. Don't hedge ("you might want to", "consider doing"). The banned phrases below (em-dashes, "here's the thing", "it's worth noting") sound conversational but are LLM crutches that add no information.

## Paragraph Density

One rule governs paragraph structure: **if removing a sentence wouldn't confuse the reader about the remaining sentences in that paragraph, it belongs in a different paragraph.**

Merge related facts so they flow. Split unrelated facts so readers scanning first-lines can identify each topic. Between paragraphs that cover different sub-topics under one heading, a short linking phrase ("For auth,...", "On the persistence side,...") signals the subject shifted.

Don't repeat the same information as a principle, a callout, and inline prose. State it once, in the location where the reader needs it.

## Contextualizing Code

Every code block needs two things:

1. **Before:** a sentence explaining what this configures or when you'd use it
2. **After:** a sentence connecting the result back to the reader's workflow (what behavior this enables, what would be different without it, or what to do next)

Exception: in pure-reference sections where the reader is looking up syntax, the surrounding prose can be minimal. The rule targets tutorial/onboarding sections where code appears without context.

Show the **generic pattern first**, then a **concrete example**:

```
tool command <placeholder> --flag <placeholder>
```

"For example, running the smoke test:"

```
tool command packages/my-pkg/src/launch.py --flag recipes/smoke/config
```

### Transitions Before Code

Never go from heading straight to a code block with no grounding sentence. Use varied openings; don't repeat the same structure (e.g., "Once you X...") in consecutive sections. Check that no two adjacent sections open with the same syntactic shape.

## Anti-Patterns

### AI-Generated Text Tells

Remove on sight:

- Em-dashes (—): use periods, commas, or restructure
- "Here's the pitch" / "Here's the thing": state the information directly
- Triple-benefit lists: "Three things X gives you: 1)... 2)... 3)..."
- "Simply" / "just": filler implying triviality
- "It's worth noting" / "One thing to keep in mind": state the fact
- Callouts restating what surrounding prose already said
- Rhetorical questions as section openers: "Want faster iteration?"
- "Whether...or..." balance constructions
- "In addition to" / "Furthermore" / "Moreover": restructure the sentence

### Structural Anti-Patterns

- **Sections that sell:** if nothing changed for the reader, don't dedicate a heading to "What Stays the Same"
- **Orphan imperatives:** paragraphs starting with a bare command without framing why or when
- **Repeated information:** the same fact in the intro, a callout, and the section body

## Revising a Document

When rewriting an existing doc:

1. **Section by section.** Critique each for: AI tells, structural issues, missing context, unnecessary content, density problems.
2. **Apply, then show.** Apply each section's edits and show a short before/after. Pause after each section only when the user asked to go section by section.
3. **End-to-end consistency pass.** After section edits, re-read for: repeated transition patterns, inconsistent terminology, remaining terse spots, and audience fit.

**Keep what the reader cut out.** When asked to shorten, simplify or drop sections, cut them and don't reintroduce the framing in later passes.

**Every paragraph adds something new.** A paragraph that restates an earlier section, a callout or the introduction gets cut or merged.

**Describe moving numbers qualitatively.** Counts, sizes and dates that will change ("20 teams", "3 incidents") go stale. Say "growing" or "several" and link the source that holds the live number.

**Rationale is prose.** Explain a decision in connected sentences under a heading that names the decision, not a bullet list under "Why".

**Long-lived documents hold durable content.** Findings tied to one project, sprint or person belong in that project's notes; link to them instead of copying them into reference docs, specs or RFCs.

## References

| Reference | When to read |
|---|---|
| `references/docs.md` | Section anatomy, callouts, routing tables, troubleshooting entries, operational details: structuring docs, runbooks and specs. |
| `references/documentation-patterns.md` | Diátaxis quadrants, BLUF, code examples as first-class content: choosing what kind of document to write. |
