---
name: skill-creator
description: Use when creating a new skill from scratch, editing or optimizing an existing skill, running evals to test a skill, benchmarking skill performance with variance analysis, or optimizing a skill's description for better triggering accuracy.
---

# Skill Creator

A skill for creating new skills and iteratively improving them.

At a high level, the process of creating a skill goes like this:

- Decide what you want the skill to do and roughly how it should do it
- Write a draft of the skill
- Create a few test prompts and run an agent-with-access-to-the-skill on them
- Help the user evaluate the results both qualitatively and quantitatively
  - While the runs happen in the background, draft some quantitative evals if there aren't any (if there are some, you can either use as is or modify if you feel something needs to change about them). Then explain them to the user (or if they already existed, explain the ones that already exist)
  - Present the results to the user for review, and also let them look at the quantitative metrics
- Rewrite the skill based on feedback from the user's evaluation of the results (and also if there are any glaring flaws that become apparent from the quantitative benchmarks)
- Repeat until you're satisfied
- Expand the test set and try again at larger scale

Your job when using this skill is to figure out where the user is in this process and then jump in and help them progress through these stages. So for instance, maybe they're like "I want to make a skill for X". You can help narrow down what they mean, write a draft, write the test cases, figure out how they want to evaluate, run all the prompts, and repeat.

On the other hand, maybe they already have a draft of the skill. In this case you can go straight to the eval/iterate part of the loop.

Of course, you should always be flexible and if the user is like "I don't need to run a bunch of evaluations, just vibe with me", you can do that instead.

Then after the skill is done (but again, the order is flexible), you can also optimize the skill description to improve triggering accuracy.

Cool? Cool.

## Why Skill Design Matters

[SkillsBench](https://arxiv.org/abs/2602.12670) (Li et al., 2026) evaluated 7,308 agent trajectories across 86 tasks and found that skill design is the primary lever for agent effectiveness:

- **Compact skills outperform comprehensive documentation by ~3x.** Focused procedural knowledge (+18.9pp) beats exhaustive reference material (+5.7pp). This is why progressive disclosure matters — keep the SKILL.md focused and put reference material one level deeper.
- **2-3 focused modules per task are optimal** (+20.0pp). Adding more modules shows diminishing returns (+5.2pp at 4+). When a skill covers many domains, use `references/` to keep the SKILL.md lean.
- **Working examples drive the largest gains.** The jump from guidance-only to guidance-with-examples was the single biggest improvement observed. Every skill should include concrete input/output pairs or worked examples.
- **Models cannot reliably self-generate effective skills.** Self-generated skills provide no benefit on average — human-curated domain expertise is what makes skills valuable. This is exactly why this skill exists.

These findings inform everything below. When in doubt, choose focused over comprehensive, concrete over abstract, and slim over thorough.

## Communicating with the user

The skill creator is liable to be used by people across a wide range of familiarity with coding jargon. There's a trend now where the power of LLMs is inspiring non-developers to open up their terminals. On the other hand, the bulk of users are probably fairly computer-literate.

So please pay attention to context cues to understand how to phrase your communication! In the default case, just to give you some idea:

- "evaluation" and "benchmark" are borderline, but OK
- for "JSON" and "assertion" you want to see serious cues from the user that they know what those things are before using them without explaining them

It's OK to briefly explain terms if you're in doubt, and feel free to clarify terms with a short definition if you're unsure if the user will get it.

---

## Creating a skill

### Capture Intent

Start by understanding the user's intent. The current conversation might already contain a workflow the user wants to capture (e.g., they say "turn this into a skill"). If so, extract answers from the conversation history first — the tools used, the sequence of steps, corrections the user made, input/output formats observed. The user may need to fill the gaps, and should confirm before proceeding to the next step.

1. What should this skill enable the model to do?
2. When should this skill trigger? (what user phrases/contexts)
3. What's the expected output format?
4. Should we set up test cases to verify the skill works? Skills with objectively verifiable outputs (file transforms, data extraction, code generation, fixed workflow steps) benefit from test cases. Skills with subjective outputs (writing style, art) often don't need them. Suggest the appropriate default based on the skill type, but let the user decide.

### Interview and Research

Proactively ask questions about edge cases, input/output formats, example files, success criteria, and dependencies. Wait to write test prompts until you've got this part ironed out.

Check available tools — if useful for research (searching docs, finding similar skills, looking up best practices), research in parallel via subagents if available, otherwise inline. Come prepared with context to reduce burden on the user.

### Write the SKILL.md

Based on the user interview, fill in these components:

- **name**: Skill identifier
- **description**: When to trigger. This is the primary triggering mechanism — include specific contexts, symptoms, and situations that should invoke the skill. All "when to use" info goes here, not in the body. Note: models tend to "undertrigger" skills — to not use them when they'd be useful. To combat this, make the skill descriptions a little bit "pushy". So for instance, instead of "Use when the user wants to display internal data.", you might write "Use when the user wants to display internal data. Make sure to use this skill whenever the user mentions dashboards, data visualization, internal metrics, or wants to display any kind of data, even if they don't explicitly ask for a 'dashboard.'"

  **Important — don't summarize the workflow in the description.** Descriptions that explain *how* the skill works (e.g., "dispatches subagents per task with code review between tasks") create a shortcut: the agent reads the description and follows that summary instead of loading and reading the full skill. The description should only describe *when* to trigger. The "Description Anti-Pattern: Workflow Summaries" section under Description Optimization has concrete before/after examples.
- **compatibility**: Required tools, dependencies (optional, rarely needed)
- **the rest of the skill :)**

### Skill Writing Guide

#### Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/    - Executable code for deterministic/repetitive tasks
    ├── references/ - Docs loaded into context as needed
    └── assets/     - Files used in output (templates, icons, fonts)
```

#### Progressive Disclosure

Skills use a three-level loading system:
1. **Metadata** (name + description) - Always in context (~100 words)
2. **SKILL.md body** - In context whenever skill triggers (<500 lines ideal)
3. **Bundled resources** - As needed (unlimited, scripts can execute without loading)

These word counts are approximate and you can feel free to go longer if needed. The SkillsBench data shows why this matters: compact, focused skills outperform sprawling documentation. Every token in the SKILL.md competes with the user's actual task for context window space.

**Key patterns:**
- Keep SKILL.md under 500 lines; if you're approaching this limit, move supplementary material into `references/` with clear pointers about when to read each file.
- Aim for 2-3 focused modules in the SKILL.md body. More than that shows diminishing returns.
- Reference files clearly from SKILL.md with guidance on when to read them
- For large reference files (>300 lines), include a table of contents

**Domain organization**: When a skill supports multiple domains/frameworks, organize by variant:
```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```
The model reads only the relevant reference file.

#### Principle of Lack of Surprise

This goes without saying, but skills must not contain malware, exploit code, or any content that could compromise system security. A skill's contents should not surprise the user in their intent if described. Don't go along with requests to create misleading skills or skills designed to facilitate unauthorized access, data exfiltration, or other malicious activities. Things like a "roleplay as an XYZ" are OK though.

#### Writing Patterns

Prefer using the imperative form in instructions.

**Defining output formats** - You can do it like this:
```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

**Examples pattern** - The SkillsBench data shows that working examples are the single biggest lever for skill effectiveness. Include concrete input/output pairs, templates, or code patterns — abstract guidance without examples underperforms. Format them like this (but if "Input" and "Output" are in the examples you might want to deviate a little):
```markdown
## Commit message format
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

### Writing Style

Try to explain to the model why things are important in lieu of heavy-handed musty MUSTs. Use theory of mind and try to make the skill general and not super-narrow to specific examples. Start by writing a draft and then look at it with fresh eyes and improve it.

For skills that need to enforce discipline or stay lean under pressure, see the hardening patterns below.

### Skill Hardening Patterns

A few patterns that come up when writing skills that need to be effective and robust in practice.

#### Anti-Rationalization (for discipline-enforcing skills)

Skills that enforce discipline — TDD, verification steps, mandatory reviews — need to resist agent rationalization. Agents are smart and find loopholes under pressure. If your skill is the kind that says "you must do X before Y", consider these techniques:

- **Rationalization tables**: During testing, capture the excuses agents use to skip steps, then add explicit counters. A `| Excuse | Reality |` table works well.
- **Red-flag lists**: Make self-checking easy. "If you catch yourself thinking X, stop." is more effective than a general rule.
- **Close loopholes explicitly**: Don't just state the rule — forbid the specific workarounds. "Delete means delete. Not 'keep as reference', not 'adapt while writing tests'."
- **Spirit vs letter**: Add "violating the letter of these rules is violating the spirit" early in discipline skills to cut off "I'm following the intent" rationalizations.

These patterns apply to discipline-enforcing skills. Technique skills and reference skills generally don't need them.

#### Token Efficiency

The SkillsBench data already tells us compact skills outperform comprehensive ones. Some concrete targets:

- **Frequently-loaded skills** (triggers on many conversations): aim for <200 words in the SKILL.md body
- **Standard skills**: <500 words is ideal (note: the Progressive Disclosure section sets a 500-*line* limit for the whole file — these are complementary, not the same target)
- **Heavy reference material**: move to `references/` subdirectories with clear pointers about when to read each file

Techniques for staying lean: reference `--help` instead of documenting all flags inline; cross-reference other skills instead of repeating their content; one excellent example beats three mediocre ones; don't repeat what's in cross-referenced skills.

#### Flowchart Usage

Flowcharts (graphviz dot, Mermaid, etc.) help in specific situations and hurt in others.

**Use flowcharts for:**
- Non-obvious decision points where the agent might go wrong
- Process loops where the agent might stop too early
- "When to use A vs B" decisions

**Don't use flowcharts for:**
- Reference material (use tables or lists)
- Code examples (use markdown code blocks)
- Linear instructions (use numbered lists)
- Labels without semantic meaning ("step1", "helper2")

### Test Cases

After writing the skill draft, come up with 2-3 realistic test prompts — the kind of thing a real user would actually say. Share them with the user: [you don't have to use this exact language] "Here are a few test cases I'd like to try. Do these look right, or do you want to add more?" Then run them.

Save test cases to `evals/evals.json`. Don't write assertions yet — just the prompts. You'll draft assertions in the next step while the runs are in progress.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

See `references/schemas.md` for the full schema (including the `assertions` field, which you'll add later).

## Running and evaluating test cases

This section is one continuous sequence — don't stop partway through.

Put results in `<skill-name>-workspace/` as a sibling to the skill directory. Within the workspace, organize results by iteration (`iteration-1/`, `iteration-2/`, etc.) and within that, each test case gets a directory (`eval-0/`, `eval-1/`, etc.). Don't create all of this upfront — just create directories as you go.

### Step 1: Spawn all runs (with-skill AND baseline) in the same turn

For each test case, spawn two subagents in the same turn — one with the skill, one without. This is important: don't spawn the with-skill runs first and then come back for baselines later. Launch everything at once so it all finishes around the same time.

**With-skill run:**

```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files if any, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about — e.g., "the .docx file", "the final CSV">
```

**Baseline run** (same prompt, but the baseline depends on context):
- **Creating a new skill**: no skill at all. Same prompt, no skill path, save to `without_skill/outputs/`.
- **Improving an existing skill**: the old version. Before editing, snapshot the skill (`cp -r <skill-path> <workspace>/skill-snapshot/`), then point the baseline subagent at the snapshot. Save to `old_skill/outputs/`.

Write an `eval_metadata.json` for each test case (assertions can be empty for now). Give each eval a descriptive name based on what it's testing — not just "eval-0". Use this name for the directory too.

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

### Step 2: While runs are in progress, draft assertions

Don't just wait for the runs to finish — you can use this time productively. Draft quantitative assertions for each test case and explain them to the user. If assertions already exist in `evals/evals.json`, review them and explain what they check.

Good assertions are objectively verifiable and have descriptive names — they should read clearly so someone glancing at the results immediately understands what each one checks. Subjective skills (writing style, design quality) are better evaluated qualitatively — don't force assertions onto things that need human judgment.

Update the `eval_metadata.json` files and `evals/evals.json` with the assertions once drafted.

### Step 3: As runs complete, capture timing data

When each subagent task completes, capture any available timing and token data immediately to `timing.json` in the run directory — this data may not be persisted elsewhere.

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

### Step 4: Grade, aggregate, and present results

Once all runs are done:

1. **Grade each run** — spawn a grader subagent (or grade inline) that reads `agents/grader.md` and evaluates each assertion against the outputs. Save results to `grading.json` in each run directory. The grading.json expectations array must use the fields `text`, `passed`, and `evidence` (not `name`/`met`/`details` or other variants). For assertions that can be checked programmatically, write and run a script rather than eyeballing it — scripts are faster, more reliable, and can be reused across iterations.

2. **Aggregate into benchmark** — collect grading results across all runs into a `benchmark.json`. See `references/schemas.md` for the exact schema. Include pass_rate, time, and tokens for each configuration, with mean ± stddev and the delta. Put each with_skill version before its baseline counterpart.

3. **Do an analyst pass** — read the benchmark data and surface patterns the aggregate stats might hide. See `agents/analyzer.md` (the "Analyzing Benchmark Results" section) for what to look for — things like assertions that always pass regardless of skill (non-discriminating), high-variance evals (possibly flaky), and time/token tradeoffs.

4. **Present results to the user** — show the qualitative outputs and quantitative benchmark data. The user needs to see both the actual outputs and the aggregate metrics to make informed decisions. Tell them something like: "Here are the results. Take a look at the outputs for each test case and let me know what you think."

### Step 5: Read the feedback

When the user provides feedback, focus improvements on the test cases where they had specific complaints. Empty feedback or "looks good" means they were satisfied with that case.

---

## Improving the skill

This is the heart of the loop. You've run the test cases, the user has reviewed the results, and now you need to make the skill better based on their feedback.

### How to think about improvements

1. **Generalize from the feedback.** The big picture thing that's happening here is that we're trying to create skills that can be used a million times (maybe literally, maybe even more who knows) across many different prompts. Here you and the user are iterating on only a few examples over and over again because it helps move faster. The user knows these examples in and out and it's quick for them to assess new outputs. But if the skill you and the user are codeveloping works only for those examples, it's useless. Rather than put in fiddly overfitty changes, or oppressively constrictive MUSTs, if there's some stubborn issue, you might try branching out and using different metaphors, or recommending different patterns of working. It's relatively cheap to try and maybe you'll land on something great.

2. **Keep the prompt lean.** Remove things that aren't pulling their weight. Make sure to read the transcripts, not just the final outputs — if it looks like the skill is making the model waste a bunch of time doing things that are unproductive, you can try getting rid of the parts of the skill that are making it do that and seeing what happens.

3. **Explain the why.** Try hard to explain the **why** behind everything you're asking the model to do. Today's LLMs are *smart*. They have good theory of mind and when given a good harness can go beyond rote instructions and really make things happen. Even if the feedback from the user is terse or frustrated, try to actually understand the task and why the user is writing what they wrote, and what they actually wrote, and then transmit this understanding into the instructions. If you find yourself writing ALWAYS or NEVER in all caps, or using super rigid structures, that's a yellow flag — if possible, reframe and explain the reasoning so that the model understands why the thing you're asking for is important. That's a more humane, powerful, and effective approach.

4. **Look for repeated work across test cases.** Read the transcripts from the test runs and notice if the subagents all independently wrote similar helper scripts or took the same multi-step approach to something. If all 3 test cases resulted in the subagent writing a `create_docx.py` or a `build_chart.py`, that's a strong signal the skill should bundle that script. Write it once, put it in `scripts/`, and tell the skill to use it. This saves every future invocation from reinventing the wheel.

This task is pretty important and your thinking time is not the blocker; take your time and really mull things over. I'd suggest writing a draft revision and then looking at it anew and making improvements. Really do your best to get into the head of the user and understand what they want and need.

### The iteration loop

After improving the skill:

1. Apply your improvements to the skill
2. Rerun all test cases into a new `iteration-<N+1>/` directory, including baseline runs. If you're creating a new skill, the baseline is always `without_skill` (no skill) — that stays the same across iterations. If you're improving an existing skill, use your judgment on what makes sense as the baseline: the original version the user came in with, or the previous iteration.
3. Present the new results to the user, ideally alongside the previous iteration for comparison
4. Wait for the user to review and tell you they're done
5. Read the new feedback, improve again, repeat

Keep going until:
- The user says they're happy
- The feedback is all empty (everything looks good)
- You're not making meaningful progress

---

## Advanced: Blind comparison

For situations where you want a more rigorous comparison between two versions of a skill (e.g., the user asks "is the new version actually better?"), there's a blind comparison system. Read `agents/comparator.md` and `agents/analyzer.md` for the details. The basic idea is: give two outputs to an independent agent without telling it which is which, and let it judge quality. Then analyze why the winner won.

This is optional, requires subagents, and most users won't need it. The human review loop is usually sufficient.

---

## Description Optimization

The description field in SKILL.md frontmatter is the primary mechanism that determines whether a model invokes a skill. After creating or improving a skill, offer to optimize the description for better triggering accuracy.

### Description Anti-Pattern: Workflow Summaries

The description field has a subtle failure mode: **if the description summarizes the skill's workflow, the agent will follow that summary instead of reading the full skill.**

Testing showed this concretely: a description saying "dispatches subagents per task with code review between tasks" caused agents to do *one* review, even though the skill's flowchart showed *two* (spec compliance, then code quality). When the description was changed to triggering conditions only, agents correctly loaded and followed the full skill.

So: descriptions should only describe *when* to trigger — the skill body handles the rest.

```yaml
# (description field only — not full frontmatter)

# BAD: summarizes workflow — agent follows this instead of reading the skill
description: Use when executing plans - dispatches subagent per task with code review between tasks

# BAD: too much process detail
description: Use for TDD - write test first, watch it fail, write minimal code, refactor

# GOOD: just triggering conditions
description: Use when executing implementation plans with independent tasks in the current session

# GOOD: triggering conditions only
description: Use when implementing any feature or bugfix, before writing implementation code
```

Start descriptions with "Use when..." and focus on: what the user is trying to do, what situation they're in, what symptoms or contexts should trigger the skill. The skill body handles the rest.

### Step 1: Generate trigger eval queries

Create 20 eval queries — a mix of should-trigger and should-not-trigger. Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

The queries must be realistic and something a user would actually type. Not abstract requests, but requests that are concrete and specific and have a good amount of detail. For instance, file paths, personal context about the user's job or situation, column names and values, company names, URLs. A little bit of backstory. Some might be in lowercase or contain abbreviations or typos or casual speech. Use a mix of different lengths, and focus on edge cases rather than making them clear-cut (the user will get a chance to sign off on them).

Bad: `"Format this data"`, `"Extract text from PDF"`, `"Create a chart"`

Good: `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

For the **should-trigger** queries (8-10), think about coverage. You want different phrasings of the same intent — some formal, some casual. Include cases where the user doesn't explicitly name the skill or file type but clearly needs it. Throw in some uncommon use cases and cases where this skill competes with another but should win.

For the **should-not-trigger** queries (8-10), the most valuable ones are the near-misses — queries that share keywords or concepts with the skill but actually need something different. Think adjacent domains, ambiguous phrasing where a naive keyword match would trigger but shouldn't, and cases where the query touches on something the skill does but in a context where another tool is more appropriate.

The key thing to avoid: don't make should-not-trigger queries obviously irrelevant. "Write a fibonacci function" as a negative test for a PDF skill is too easy — it doesn't test anything. The negative cases should be genuinely tricky.

### Step 2: Review with user

Present the eval set to the user for review. Let them edit queries, toggle should-trigger, and add/remove entries. This step matters — bad eval queries lead to bad descriptions.

### Step 3: Test and refine

Test trigger accuracy by running each query and checking whether the skill triggers as expected. Adjust the description based on what's failing — missed triggers usually mean the description doesn't cover that phrasing; false triggers mean the description is too broad.

### How skill triggering works

Understanding the triggering mechanism helps design better eval queries. Skills appear in the model's `available_skills` list with their name + description, and the model decides whether to consult a skill based on that description. The important thing to know is that models only consult skills for tasks they can't easily handle on their own — simple, one-step queries like "read this PDF" may not trigger a skill even if the description matches perfectly, because the model can handle them directly with basic tools. Complex, multi-step, or specialized queries reliably trigger skills when the description matches.

This means your eval queries should be substantive enough that the model would actually benefit from consulting a skill. Simple queries like "read file X" are poor test cases — they won't trigger skills regardless of description quality.

### Step 4: Apply the result

Update the skill's SKILL.md frontmatter with the improved description. Show the user before/after and report the accuracy scores.

The goal is high precision on near-miss negatives while maintaining recall on varied phrasings of legitimate use cases.

---

## Updating an existing skill

The user might be asking you to update an existing skill, not create a new one. In this case:

- **Preserve the original name.** Note the skill's directory name and `name` frontmatter field — use them unchanged.
- **Copy to a writeable location before editing.** The installed skill path may be read-only.
- **Focus changes on the specific issue identified** — don't rewrite what's working.

---

## Reference files

The agents/ directory contains instructions for specialized subagents. Read them when you need to spawn the relevant subagent.

- `agents/grader.md` — How to evaluate assertions against outputs
- `agents/comparator.md` — How to do blind A/B comparison between two outputs
- `agents/analyzer.md` — How to analyze why one version beat another

The references/ directory has additional documentation:
- `references/schemas.md` — JSON structures for evals.json, grading.json, benchmark.json, etc.

---

Repeating one more time the core loop here for emphasis:

- Figure out what the skill is about
- Draft or edit the skill
- Run an agent-with-access-to-the-skill on test prompts
- With the user, evaluate the outputs (qualitative review + quantitative benchmarks)
- Repeat until you and the user are satisfied

Good luck!
