# Document Structure Patterns


### Section Anatomy

Major sections follow this shape (skip what doesn't apply):

1. **Concept callout** (only for sections representing a key term, and only when readers commonly land here via link without reading earlier sections)
2. **Context paragraph**: what this section covers, optionally contrasting with what it replaces
3. **Routing table** (only when multiple paths exist)
4. **Subsections with code**

### Concept Callouts

Place a definition callout at the top of sections that map to a defined term, when readers commonly arrive mid-page via shared links. Adapt the format to the platform (Markdown admonitions, wiki callouts or info panels).

This intentionally duplicates the concepts table for jump-linked readers. Limit to sections representing core terms (3-5 per doc max). If most sections need one, the doc might need restructuring instead.

### Callout Hierarchy

Use callouts with consistent semantic meaning. Here's a starter palette to customize for your domain:

| Purpose | When to use |
|---------|-------------|
| Concept definition | Top of sections mapping to key terms |
| Tip or insight | Non-obvious behavior, mental model shifts |
| Warning or sharp edge | Things that break or confuse if missed |
| Prerequisite | Steps that must happen before something else works |
| Operational state | What persists, what doesn't, where data lives |

No more than 2-3 callouts per major section. If you have more, the most important information should be in prose, not callouts.

### Routing Tables

When multiple paths exist (CLI vs UI, quick vs committed, interactive vs scripted), open with a table:

| Path | What it does | When to use it |
|------|-------------|----------------|
| `option-a` | Short description | Use case |
| `option-b` | Short description | Use case |

Each path then gets its own subsection.

### Usage-Mode Organization

When a system can be used in fundamentally different ways, organize by what the reader is trying to accomplish, not by tool or command. To identify modes: list the 2-4 distinct goals a reader might arrive with. Use those as headings.

### Diagrams

If you can express a relationship as a numbered list or before/after pair, don't use a diagram. Use diagrams only when the reader needs to see that step N loops back to step M, or that multiple paths converge on one outcome.

### Troubleshooting Entries

Consistent structure per entry:

- **Symptom:** what the user observes
- **Cause:** technical root cause
- **Fix:** what to do (actionable, with code if needed)
- **Ticket:** link if tracked

### Operational Details

Document the operational realities users encounter, placed inline where the reader will hit the behavior (not in a separate "notes" section):

- **State and persistence:** what survives restarts, what doesn't
- **Credential lifecycle:** when they expire, how to re-auth, where they live (if applicable)
- **Version requirements:** at the point the reader needs the capability

### Contrast Paragraphs (for adoption/migration contexts)

When introducing something that replaces an existing workflow, define it by contrast: "Without [new thing], [how it works today]. [New thing] does the same work, but [key difference]." Skip this pattern for net-new systems with no prior workflow.

### Multiple Interface Paths

When both CLI and UI paths exist, document them as sibling subsections. Note capability gaps in a callout if one path is limited. Skip this structure when only one interface exists.
