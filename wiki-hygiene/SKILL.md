---
name: "wiki-hygiene"
summary: "Scan the knowledge base for stale notes, orphans, and frontmatter inconsistencies"
type: "process"
description: "Load when the user asks about wiki health, stale notes, wiki hygiene, wiki cleanup, or 'check the wiki'. Produces a read-only staleness report — never auto-modifies notes. NOT for reading or writing wiki content (that's the knowledge-base skill)."
---

# Wiki Hygiene

Scan `~/llm-wiki` and produce a staleness report. **Report only — never auto-modify notes.**

The wiki is git-backed, Obsidian-style markdown. Frontmatter is YAML between `---` delimiters. Wikilinks use `[[path]]` or `[[path|display]]` format. The user values this as a human-readable journal of record — conservative approach only.

## Wiki location

Read from `~/llm-wiki`. If absent, check `AGENTS.md` for `Knowledge base: <path>`. If neither resolves, ask the user.

## Note types for reference

topic (~340), decision (~30), person (~29), plan (~3), moc (~3), org (~2).

---

## Staleness signals to detect

### 1. Stale active decisions

Decision notes (`type: decision`) with `status: active` where `updated:` is >90 days old.

```bash
# Find decision files, extract updated date and status, compare to 90-day threshold
THRESHOLD=$(date -v-90d +%Y-%m-%d 2>/dev/null || date -d '90 days ago' +%Y-%m-%d)
find ~/llm-wiki/decisions -name '*.md' -exec grep -l 'status: active' {} \; | while read f; do
  updated=$(awk '/^---$/{n++} n==1 && /^updated:/{print $2; exit}' "$f")
  if [[ "$updated" < "$THRESHOLD" ]]; then
    echo "$f|stale-active|updated: $updated"
  fi
done
```

### 2. Decisions missing status field

Decision notes (`type: decision`) with no `status:` line in frontmatter.

```bash
find ~/llm-wiki/decisions -name '*.md' | while read f; do
  # Extract frontmatter (between first two --- lines), check for status
  if awk '/^---$/{n++; next} n==1{print} n==2{exit}' "$f" | grep -q '^type: decision' && \
     ! awk '/^---$/{n++; next} n==1{print} n==2{exit}' "$f" | grep -qi '^status:'; then
    echo "$f|missing-status"
  fi
done
```

### 3. Orphan notes (zero inbound wikilinks)

Notes not referenced by any `[[...]]` link in any other file. MOCs and `INDEX.md` are excluded from being flagged as orphans (they are entry points, not targets).

```bash
# Build a set of all wikilink targets across the wiki
grep -roh '\[\[[^]|]*' ~/llm-wiki --include='*.md' | sed 's/\[\[//' | sort -u > /tmp/wiki-link-targets.txt

# Check each note for inbound links
find ~/llm-wiki -name '*.md' | while read f; do
  # Derive the linkable slug (e.g., "people/jordan" from "people/jordan.md")
  slug=$(echo "$f" | sed "s|^$HOME/llm-wiki/||; s|\.md$||")
  basename_slug=$(basename "$slug")
  # Skip INDEX.md and MOCs — they're entry points
  [[ "$slug" == "INDEX" ]] && continue
  echo "$slug" | grep -q '^moc/' && continue
  # Check if any link target matches this slug
  if ! grep -qxF "$slug" /tmp/wiki-link-targets.txt && \
     ! grep -qxF "$basename_slug" /tmp/wiki-link-targets.txt; then
    echo "$f|orphan"
  fi
done
```

### 4. Frontmatter inconsistencies

**Missing required fields:**
- All notes: `related:`, plus `aliases:` for topic notes
- Decision notes: `decision_date:`

**Case mismatches:** Field names should be lowercase. Flag `Related:`, `Aliases:`, `Tags:`, `Decision_date:`, etc.

```bash
find ~/llm-wiki -name '*.md' | while read f; do
  fm=$(awk '/^---$/{n++; next} n==1{print} n>=2{exit}' "$f")
  type=$(echo "$fm" | awk '/^type:/{print $2}')

  # Case mismatches — check for capitalized field names
  echo "$fm" | grep -E '^[A-Z][a-z_]+:' | while read line; do
    field=$(echo "$line" | cut -d: -f1)
    echo "$f|case-mismatch|field '$field' should be lowercase"
  done

  # Missing related: (all types)
  if ! echo "$fm" | grep -q '^related:'; then
    echo "$f|missing-field|related"
  fi

  # Missing aliases: (topics)
  if [[ "$type" == "topic" ]] && ! echo "$fm" | grep -q '^aliases:'; then
    echo "$f|missing-field|aliases (required for topics)"
  fi

  # Missing decision_date: (decisions)
  if [[ "$type" == "decision" ]] && ! echo "$fm" | grep -q '^decision_date:'; then
    echo "$f|missing-field|decision_date (required for decisions)"
  fi
done
```

---

## Output format

Print a structured markdown report to **stdout**. Do not write to a file unless the user explicitly asks.

```markdown
# Wiki Hygiene Report

_Scanned: YYYY-MM-DD — N total notes_

## Stale Active Decisions (>90 days)
| File | Last Updated |
|------|-------------|
| `decisions/2025-01-15-example.md` | 2025-01-15 |

## Decisions Missing Status
- `decisions/2024-12-01-example.md`

## Orphan Notes (zero inbound links)
- `topics/forgotten-thing.md`
- `people/someone.md`

## Frontmatter Issues
| File | Issue |
|------|-------|
| `topics/foo.md` | missing field: `aliases` |
| `decisions/bar.md` | missing field: `decision_date` |
| `topics/baz.md` | case mismatch: `Related:` → `related:` |

## Summary
- Stale decisions: N
- Missing status: N
- Orphans: N
- Frontmatter issues: N
```

If a section has zero findings, include it with "None found ✓".

---

## Execution notes

- Use `find`, `grep`, `awk`, `sed`, `sort` — no external dependencies.
- On macOS, `date -v-90d` works; on Linux use `date -d '90 days ago'`. Handle both.
- Run all scans in a single bash invocation to keep the report atomic.
- For orphan detection, normalize paths by stripping the wiki root and `.md` extension when comparing against wikilink targets.
- Large wikis (~400 notes): the scan should complete in seconds. No optimization needed beyond basic shell.

## Anti-patterns

- **Never modify notes.** This skill is read-only. If the user wants fixes, they ask explicitly and the knowledge-base skill handles writes.
- **Don't auto-run on session start.** Only run when triggered by the user.
- **Don't flag notes as stale just because they're old.** Only flag active decisions past the threshold. Old topic notes are fine.
- **Don't treat MOCs or INDEX.md as orphans.** They are graph entry points.
