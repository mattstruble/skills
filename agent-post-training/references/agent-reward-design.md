# Agent Reward Design

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## The Reward Density Spectrum

Reward signals range from sparse to dense. The right choice depends on the task structure and what can be reliably verified.

```
sparse ←————————————————————————————→ dense
binary reward    milestone reward    process reward    dense continuous
(0/1 at end)     (partial credit)    (per-step)        (per-token)
```

**Binary outcome rewards** (success=1, failure=0) are sufficient for tasks with clear correct answers: math problems, SQL queries, code tests. Simple, reliable, no annotation overhead. The problem arises with open-ended tasks or long multi-step sequences where the model can fail in many different ways — a binary signal at the end provides no guidance on which step went wrong.

**The sparse reward dilemma.** In a 10-step process, even if the first nine steps are perfect and only the tenth fails, the signal is still "the whole task failed" — with no way to tell which step was at fault. A phone-calling agent that fails because it forgot to collect the billing address receives the same reward=0 as one that failed because it called the wrong number. The model cannot learn from the rich feedback the environment provides.

**Process rewards** provide immediate feedback at each key step, transforming evaluation from a black box to a white box. In code generation: separate scores for requirement understanding, code search, solution design, code writing, test running. In customer service: separate checks for identity verification, information query, confirmation, payment. Process rewards reduce credit assignment difficulty but introduce two costs: high annotation burden and risk of over-constraining exploration — the model may converge on the demonstrated process rather than discovering better strategies.

**The practical tradeoff.** Process rewards accelerate convergence through dense feedback but may prevent the model from breaking out of the demonstration space. Outcome rewards give maximum exploration freedom — this is how novel strategies emerge that no demonstrator ever showed — but require more training and samples. When the correctness of intermediate steps is easy to define, process rewards are more efficient. When the optimal path is unknown, outcome rewards have more potential.

---

## Process vs Outcome Reward: The Key Choice

**Process Reward Model (PRM):** Scores each intermediate step of reasoning or execution. Reduces credit assignment difficulty. Risk: may over-constrain the strategy space, preventing discovery of better approaches.

**Outcome Reward Model (ORM):** Evaluates only the final result. Maximum exploration freedom. A rule-based verifier (test pass/fail, answer matches key) is a special case of ORM — deterministic rules replacing a learned scoring model.

**In practice:** Process and outcome rewards are used together. The common pattern: outcome reward as the primary signal (the true goal), with process rewards or path penalties added to guide behavior on intermediate steps.

---

## Reward the Outcome, Constrain the Process

Pure outcome rewards have a fundamental limitation for deployable agents: they cannot express the requirement that the process must follow rules — and they actively incentivize violating those rules. Cutting corners raises apparent success rate. Agents trained on outcome rewards alone will skip identity verification, edit test files to make tests pass, run destructive commands — because these shortcuts improve the outcome metric.

**The pattern:** Outcome reward as the primary driver, plus verifiable path penalties for machine-detectable bad actions.

Total reward = Outcome reward + β × Path signal

The path signal has two components:
- **Penalty (−λ):** Deduct points for each machine-verifiable violation action (destructive command, skipping required step, modifying test files). Applied at the token level of the bad action.
- **Compliance reward (+μ):** Add points for each corresponding compliant action (actually fixing the bug rather than editing the test, completing identity verification before proceeding).

**Four design principles for path penalties:**

1. **Penalize only verifiable "actions," never "lack of progress."** The penalty target must be a specific, machine-detectable bad action. Penalizing "no progress at this step" teaches the agent to do nothing — zero violations, zero success.

2. **Outcome rewards are always the primary driver.** With only penalties and no outcome rewards, the optimal strategy is "do nothing." Outcome rewards provide the pull to complete the task; penalties only guide how.

3. **Pair each penalty with a corresponding compliance reward.** Give the agent a way out, not just a blockade. Deduct points for modifying test files, but reward actually fixing the bug to make it pass naturally.

4. **Penalty targets must be un-gameable.** Use specific, deterministic checks — not a learned "compliance score" judge. Otherwise the model games the judge instead of the task.

---

## Multi-Turn Credit Assignment

In a multi-step agent task, which step caused the final success or failure? This is the core challenge of multi-turn RL.

**The problem.** A customer service agent solves a user's problem after 10 turns and receives a positive review. Should this be attributed to the precise questioning in turn 2 or the patient explanation in turn 7? With a binary outcome reward, the model has no way to distinguish.

**Practical approaches:**

- **Discount factor γ = 1** is standard for multi-turn LLM RL. Tasks only last a few to dozens of turns; there is no need to discount rewards for "earlier success." The optimization goal is ultimate success or failure.

- **PPO with value network** estimates "how much better this step is than expected" for each step in the trajectory, providing fine-grained credit assignment. More expensive but valuable for long-horizon tasks.

- **GRPO** treats the entire response as a single action and distributes credit evenly across all tokens. A precise question in turn 2 and an ineffective pleasantry in turn 7 receive identical credit. This coarse assignment is acceptable for short single-turn tasks but dilutes the learning signal in long multi-turn tasks.

- **Turn-level credit assignment** calculates advantages at the turn level — cheaper than token-level, more precise than trajectory-level. The common compromise in current multi-turn agent RL frameworks.

---

## Tool-Calling Reward Design

Tool use introduces specific reward design challenges beyond standard multi-turn RL.

**Why RL for tool calling beats prompt engineering at scale.** Prompt engineering can specify which tools to use and when, but it cannot teach the model to recover from tool errors, discover efficient tool sequences, or adapt to novel tool combinations. RL with a verifiable reward signal (did the tool call produce the right result?) allows the model to learn these behaviors through trial and error. The ceiling of prompt engineering is the designer's knowledge of the optimal tool sequence; the ceiling of RL is the task itself.

**The three levels of tool-use difficulty:**

1. **Single tool mastery** — understanding input/output specifications, timing of calls, error handling. SFT warm-up is usually sufficient to establish basic patterns; RL then refines timing and error recovery.

2. **Multi-tool selection** — choosing among dozens of tools, deciding when to search vs. execute code vs. parse documents. This requires generalization that SFT cannot provide — the optimal selection depends on the specific query, not a memorized pattern.

3. **Tool chain orchestration** — discovering dependencies between tools, identifying mutually exclusive constraints, optimizing cost efficiency. This is the domain where RL's ability to discover novel strategies is most valuable.

**Loss masking for environment feedback tokens.** A tool call trajectory contains both tokens generated by the model (thinking, tool call parameters) and tokens returned by the environment (code interpreter output, search results). Environment feedback tokens must be masked when computing the policy gradient — the model should not be trained to predict what the sandbox will output, only to generate effective tool calls. This is a standard requirement in tool-calling RL frameworks.

**Reward signal for tool calling.** The simplest reliable signal: did the tool call produce the correct result? For code execution: did the tests pass? For search: did the retrieved content contain the answer? Binary outcome rewards are often sufficient for single-tool tasks. For multi-tool orchestration, process rewards that score each tool call independently can accelerate learning.

---

## Reward Paradigm Evolution

As tasks become more open-ended, scalar rewards become insufficient. The progression:

- **Scalar:** A single score (7.2/10). No diagnostic capability — no insight into what was done well or poorly.
- **Vector:** Separate scores per dimension (information accuracy 9/10, collection completeness 6/10, communication fluency 8/10). Precisely pinpoints which dimension needs improvement.
- **Generative:** Natural language description of execution with reasoning. Supports multiple sampling runs that analyze from different angles. Transforms rich environmental feedback into learnable knowledge — the model can learn improvement directions from a single failure rather than requiring hundreds of blind trial-and-error attempts.

**When to use each:** Binary rewards for tasks with clear correct answers. Vector rewards for tasks with multiple independent quality dimensions. Generative rewards for highly open-ended tasks that are difficult to decompose into fixed dimensions.
