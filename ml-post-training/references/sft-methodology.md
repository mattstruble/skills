# SFT Methodology

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## What SFT Actually Does

SFT and pre-training are mathematically identical — both minimize cross-entropy loss on next-token prediction. The differences are:

1. **Data**: pre-training uses raw internet text; SFT uses curated input-output pairs formatted as `user question → ideal answer`
2. **Loss masking**: loss is computed only on response tokens, not prompt tokens. The model learns to answer, not to ask.

This means SFT's optimization target is "maximize the probability of every token in the labeled response." The model is being trained to reproduce the demonstration as closely as possible. This is efficient for format and protocol learning, but it means the model's capability ceiling is set by the quality of the demonstrations.

**What SFT solidifies**: protocols (format, style, process, interaction patterns). **What SFT does not do well**: inject factual knowledge (use RAG), generalize to unseen situations (use RL), or surpass the quality of the demonstrations.

---

## Loss Masking Implementation

In a training batch, each sample has a prompt portion and a response portion. The loss mask zeros out all prompt tokens before computing cross-entropy:

```python
# Pseudocode — most frameworks handle this, but verify it's active
labels = input_ids.clone()
labels[:, :prompt_length] = -100  # -100 = ignore_index in PyTorch cross-entropy
loss = cross_entropy(logits, labels)
```

If loss masking is not applied, the model learns to predict both questions and answers, which degrades instruction-following behavior. Verify this is enabled in your training config — it is a common misconfiguration.

---

## Data Preparation

### Format Consistency

Every sample must use the same chat template. Mixing templates (e.g., some samples with system prompts, some without; different separator tokens) produces a model that outputs inconsistently. Pick one template and apply it uniformly.

Common templates: ChatML (`<|im_start|>system...`), Llama-3 (`<|begin_of_text|><|start_header_id|>...`), Alpaca (`### Instruction:...`). Match the template to the base model's pre-training format when possible.

### Quality Over Quantity

A few thousand high-quality demonstrations consistently outperform tens of thousands of noisy ones. SFT bakes noise into parameters verbatim — there is no filtering mechanism at training time. Invest in data quality before scaling data quantity.

Quality checklist:
- **Correct**: the response is factually accurate and task-complete
- **Consistent format**: response uses the target output structure (JSON schema, tool call format, etc.)
- **Appropriate length**: not truncated, not padded with filler
- **No leakage**: responses do not reveal information the model should not have at inference time

### Coverage and Diversity

SFT generalizes poorly to inputs outside the training distribution. The only mitigation is coverage — the training set must include examples from the full distribution of inputs the model will encounter at deployment.

Practical approach: sample from your actual deployment query distribution (or a proxy), cluster by intent/format, and ensure each cluster is represented. Gaps in coverage become gaps in capability.

### What SFT Cannot Do

- **Factual knowledge**: SFT is poor at memorizing facts. A model trained to answer "What is the capital of France?" will answer correctly, but a model trained on 10,000 medical facts will not reliably retain them. Use RAG for facts that need to be current, traceable, or numerous.
- **Surpass demonstrations**: the model's ceiling is the quality of the labeled data. A dataset annotated by mediocre annotators produces a mediocre model.
- **Generalize under distribution shift**: if training uses card values J/Q/K=10 and deployment uses J=11, SFT will fail. RL is required for generalization.

---

## LoRA Configuration

LoRA attaches low-rank "patch" matrices to the base model's weight matrices. The base weights are frozen; only the patches are trained. This reduces trainable parameters to 1–5% of full fine-tuning while approaching full fine-tuning performance.

### Rank Selection

| Use Case | Recommended Rank |
|---|---|
| SFT (general instruction following) | 64–256 |
| SFT (narrow task, few examples) | 32–64 |
| RL training | 8–32 |
| RL with very small per-step information | 1–8 |

Higher rank = more capacity = more parameters = higher cost. For SFT, use medium-to-high rank because each training sample carries substantial information. For RL, each rollout carries a single scalar reward signal — low rank is sufficient and cheaper.

### Learning Rate

The optimal LoRA learning rate is approximately 10× the learning rate you would use for full fine-tuning. This rule holds for both SFT and RL and transfers across model families. A common starting point: `lr = 1e-4` for LoRA when full fine-tuning would use `lr = 1e-5`.

### Target Modules

**Apply LoRA to all major weight matrices**, especially MLP layers. Applying LoRA only to attention layers (a common shortcut) costs significant accuracy because MLP layers contain the largest parameter count.

Typical target modules for transformer models:
```
q_proj, k_proj, v_proj, o_proj,  # attention
gate_proj, up_proj, down_proj     # MLP (critical — do not skip)
```

### Alpha

Alpha controls the effective learning rate of the LoRA update. A common default: `alpha = 2 × rank`. Some practitioners set `alpha = rank` for more conservative updates.

### Multi-Tenant Deployment

A single inference server can load multiple LoRA adapters simultaneously, serving different fine-tuned variants from the same base model. This is the standard pattern for multi-tenant SFT deployments.

---

## Format Stabilization

The SFT phase is complete when the model reliably produces output that the reward function can parse and score. This is the gate condition for starting RL.

**For structured-output tasks (JSON, tool calls)**: target JSON parse failure rate below ~5–10% on a held-out format evaluation set.

**For free-form tasks (CoT, dialogue)**: parse failure rate is not the right metric. Use format-agnostic proxies instead: response length distribution stability (the distribution of response lengths stops shifting), and instruction-following rate on a held-out set (the model reliably follows explicit formatting instructions like "respond in bullet points").

Stabilization recipe:
1. Start with 500–2,000 format-focused demonstrations (correct structure, varied content)
2. Evaluate the relevant stability metric every few hundred steps
3. Stop when the metric is below threshold — do not overtrain
4. Overtraining SFT collapses the model onto the training distribution, limiting RL's optimization space

If format is still unstable after 5,000+ demonstrations, the issue is likely template inconsistency or base model mismatch (the base model's pre-training format differs significantly from the target format).

**Exception — strong base models**: the SFT-first requirement holds for smaller models with strictly structured output requirements. A sufficiently strong base model may produce adequate output from the start and can attempt direct RL without SFT (DeepSeek-R1-Zero demonstrated this). The cost is poor output readability and mixed-language outputs; DeepSeek ultimately added "cold-start SFT" in R1 to re-establish format. When in doubt, run SFT first.

---

## Prompt Distillation

When a capable teacher model (e.g., DeepSeek-R1, QwQ) is available, distillation is often more efficient than annotating demonstrations from scratch.

Three-step recipe:
1. **Collect trajectories**: sample problems from the target task distribution; use the teacher to generate complete "thinking + answer" trajectories; filter out trajectories with incorrect final answers using a rule-based validator (otherwise the student imitates erroneous reasoning)
2. **SFT training**: use `problem → <think> reasoning </think> + final answer` as training pairs; standard SFT on the student model
3. **Evaluate**: compare student before/after distillation on the same benchmark; verify thinking trajectories show teacher-like behaviors (reflection, backtracking, verification)

**Cost of distillation**: the student inherits the teacher's systematic errors and verbose thinking habits. The latter can be further optimized with RL (AdaptThink pattern: train the model to skip thinking for easy questions).

**Closed-source teacher limitation**: models like OpenAI o-series rewrite or summarize their chain-of-thought before output. Use open-source reasoning models (DeepSeek-R1, QwQ) as teachers — they expose the complete chain-of-thought in `<think>` tags, making distillation feasible.
