# Simplified Technical English for Specs, PRDs and Tickets

Required for specs, PRDs, RFCs, design docs, stories and ticket bodies. Recommended for
other reference docs. Readers include people who read English as a second language,
reviewers who read the document next to the current code, and agents that parse it
without asking.

This is an 80% form of [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/):
its writing rules, with normal technical vocabulary and without its controlled
dictionary. It is a style, not STE compliance; never claim compliance. Adapted from
[prithivrajmu/asd-ste100](https://github.com/prithivrajmu/asd-ste100) (MIT).

## Meaning first

These rules win over every style rule below.

- **Keep the confidence.** "May fail" stays "may fail". Keep hypotheses conditional.
- **Keep the logic.** Keep negation, AND/OR conditions, order, actors, units, numbers
  and exceptions.
- **Add no facts.** Do not invent a cause, actor or mechanism to complete a sentence.
- **Keep literal content.** Code, identifiers, commands, paths, field names and quoted
  errors stay unchanged.
- **Flag ambiguity outside the text.** When you revise and the source is ambiguous,
  keep its wording and list the question after your revision. When you write, put it
  in the document's Open Questions section.
- **Keep the size.** A revision is about as long as the source. Do not add sections,
  labels or lists the source did not need.

## Current and proposed behavior

A reader with the current code open must know whether each sentence describes current
or proposed behavior. Mark state only from what you know: the code, the author, or the
document's own labels. Never relabel a passage on a guess; that adds a false fact.

- Use the present tense only for system behavior that exists now. For proposed
  behavior, use "will", or open the sentence with "Under this proposal," or the release
  name. A section label alone is not enough: readers skim into the middle of a section.
- Facts that hold either way (why something changes, who owns it, a constraint of the
  domain) stay in the present tense. Do not put "will" on them.
- Mark each statement about current behavior with "Today," or a "Today" column.
- Do not mix both states in one sentence.
- Mark illustrative content as illustrative: "Example field list (not final)".

## Terms

- **One term, one meaning.** Use one name for each concept everywhere. No synonyms, and
  do not use the same word for two concepts.
- **Define at first use.** Define each project term the first time it appears, or link
  its glossary entry. Do not use a term before its definition.
- **Watch everyday words.** A common word with a project meaning ("view", "image",
  "scope", "channel", "additive") gets a definition, because readers take the everyday
  or field-specific meaning first.
- **Anchor named things.** Link each function, type, field or component to where it is
  defined: the code, the API section, or the document that owns it.

## Exact outcomes

Say what the system does, not how good or bad the input is.

- Write "raises `ConfigError` at load", "is rejected by `validate`", "returns an empty
  list", not "malformed", "invalid", "not supported", "handles" or "takes care of".
- For each rule, name who checks it and when: at import, at registration, at run time,
  in review.

## Sentences

1. Put the main point first. One claim in each sentence, but keep a reason or contrast
   with its claim: "because", "so", "unless" and "while" carry logic that a split
   loses.
2. Aim for 20 words or fewer in instructions and 25 in descriptions. Split a longer
   sentence only when both halves still read as connected.
3. Use the active voice when the actor is known. Use the passive voice when it is not;
   do not invent an actor.
4. Use verbs, not noun phrases: "check the log", not "perform a check of the log".
5. Use plain words and no idioms or phrasal verbs: "start", not "spin up"; "remove",
   not "get rid of".
6. No more than three nouns in a row ("user session token cache key" is too many).
7. State a condition before its action: "If the file is empty, `load` raises
   `ConfigError`."
8. Use only "must" for requirements, "can" for permission or ability, and "will" for
   future behavior. Do not use "should", "may" or "might" for requirements.
9. Use numbered lists for ordered steps and bullets for independent items.

## Requirements and acceptance criteria

- One behavior in each statement: actor, condition, observable result. "When a request
  has no token, the API returns 401."
- Each acceptance criterion is one testable sentence that someone can mark pass or
  fail without asking the author.
- Name limits as numbers with units, or move the missing number to Open Questions.

## Tickets and stories

A ticket or story body states, in this order: the current behavior ("Today, ..."), the
required behavior, the done condition, and links to the spec sections it implements.

## Final check

Before you finish a spec, PRD, story or ticket, reread it once against this file:
tense marks current versus proposed, each project term is defined or linked, no
verdict words remain, and every requirement uses "must".
