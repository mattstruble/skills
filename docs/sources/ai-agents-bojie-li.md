# AI Agents in Depth (Bojie Li) — Source Attribution

Provenance for skill content synthesized from Bojie Li's book *AI Agents in
Depth: Design Principles and Engineering Practice* (v1.2). This file is **not
registered in any skill's References table** — it is read by humans and by
skill-building sessions, and is **never auto-loaded at skill runtime**. It
exists for human traceability and to lock shared conventions so citation
formatting stays consistent across the whole ai-agents skill family.

Source (no vendoring): [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf)

## For skill-builders (read before building an ai-agents-family skill)

Every session that distills a chapter of this book into a skill follows these
conventions so the family stays consistent.

**Official citation line.** Paste this verbatim into the intro of each new
`references/*.md` file you create (the `../../` path resolves from
`<skill>/references/`):

```
*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*
```

**Two citation rules:**

1. **Reference files** carry the official citation line in their intro. Prose
   is paraphrased and clean — no inline source tags. Present genuinely
   contestable stances inline as "Bojie Li argues…".
2. **Body weaves** — book material woven into an existing skill's `SKILL.md`
   (e.g. the Ch2 §2.5 → skill-creator weave) — carry **no citation line**.
   Record them only as a row in the map below. Attribute contestable stances
   inline as "Bojie Li argues…"; weave non-contestable technique as plain
   content.

**Other rules:**

- **Conceptual filenames.** Name reference files by concept (e.g.
  `harness-engineering.md`), never `bojie-*`.
- **Paraphrase only.** No verbatim quotes from the book.
- **Cite the chapter you synthesize from.** If you pull material from a
  sibling skill's chapter, add a row here for your skill rather than letting
  the attribution ride on the sibling's row.
- **Update the map.** Overwrite your row's working skill name with the final
  name your session picks, and fill in the reference file(s) you created. A
  fold is recorded by pointing your row's reference cell at the absorbing
  skill's file.

Lifecycle (pending / built / split / folded / skipped / deferred) is tracked
in beads (epic `mattstruble-skills-u9i`), not here — this file records the
durable chapter→skill→reference map only.

## Chapter map

| Chapter | Skill | Reference file(s) |
| --- | --- | --- |
| Ch1 | agent-architecture | orchestration-patterns.md, guardrails-and-safety.md |
| Ch2 (§2.1–2.4, 2.6, 2.7) | context-engineering | prompt-design.md, kv-cache-context.md, compression-strategies.md |
| Ch2 §2.5 | skill-creator (body weave) | SKILL.md body weave |
| Ch3 §3.1 | agent-memory | memory-formats.md, memory-evaluation.md |
| Ch3 §3.2-3.3 | rag-design *(planned)* | retrieval-infrastructure.md, knowledge-organization.md |
<!-- Split: audience-driven — memory-system builders (§3.1) vs retrieval-pipeline builders (§3.2-3.3) -->
| Ch4 | agent-tool-design | tool-categories.md, tool-ecosystem.md |
| Ch4 §4.7.6-4.7.8 | agent-architecture (fold) | async-event-handling.md |
| Ch5 | coding-agent-design | search-and-editing.md, code-meta-patterns.md |
| Ch6 | agent-evaluation | eval-methodology.md, eval-infrastructure.md |
| Ch7 (advisory) | agent-post-training | post-training-decisions.md, agent-reward-design.md |
| Ch7 (implementation) | ml-post-training | sft-methodology.md, rl-training.md, training-data-environment.md |
<!-- Split: audience-driven — advisory/decision layer (agent builders) vs implementation layer (ML practitioners) -->
| Ch8 | agent-self-evolution *(fold decided in-session)* | TBD |
| Ch9 | multimodal-agents *(fold/defer decided in-session)* | TBD |
| Ch10 | multi-agent-collaboration | collaboration-patterns.md, multi-agent-infrastructure.md |

Working skill names above are placeholders from the epic task graph
(`mattstruble-skills-u9i`); the final name for each skill is chosen
per-session by skill-creator and written back into the `Skill` cell.
