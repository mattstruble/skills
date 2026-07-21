# Retrieval Infrastructure

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## Embedding Model Selection

The embedding model converts text into dense vectors. Selection criteria:

| Criterion | Consideration |
|---|---|
| **Dimension** | Higher dimension → more expressive but larger index and slower retrieval. 768–1536 covers most use cases. |
| **Training domain** | Models trained on general web text underperform on specialized domains (legal, medical, code). Prefer domain-matched or fine-tuned models. |
| **Multilingual** | Multilingual models trade some monolingual quality for cross-lingual retrieval. Use only when cross-lingual queries are expected. |
| **Speed vs quality** | Smaller models (e.g., 33M params) are 10–20× faster at inference; larger models produce better semantic representations. Profile on your actual query distribution. |
| **Max sequence length** | Most models cap at 512 tokens. Chunks longer than the model's max sequence length are truncated — verify alignment with your chunk size. |

**Practical guidance**: benchmark at least two candidate models on a sample of
your actual queries before committing. Embedding quality is corpus- and
query-dependent; no single model dominates across all domains.

---

## Dense Index Structures

Dense retrieval requires an approximate nearest neighbor (ANN) index over the
embedding vectors.

### ANNOY (Approximate Nearest Neighbors Oh Yeah)

Tree-based ANN index. Builds a forest of random projection trees at index
time; queries traverse the forest to find approximate neighbors.

**Strengths:**
- Fast query time for static corpora
- Low memory footprint relative to graph-based indexes
- Simple to build and serialize

**Limitation**: does not support incremental insertion. Adding new documents
requires rebuilding the entire index. This makes ANNOY unsuitable for
frequently-updated knowledge bases.

**Use when**: the corpus is built once and queried many times (build-once,
query-many). Examples: a product catalog that updates monthly, a document
archive with infrequent additions.

### HNSW (Hierarchical Navigable Small World)

Graph-based ANN index. Builds a multi-layer proximity graph; queries traverse
from the top (coarse) layer down to the bottom (fine) layer.

**Strengths:**
- Supports incremental insertion — new documents can be added without
  rebuilding
- High recall at competitive query latency
- Scales well to hundreds of millions of vectors

**Limitation**: higher memory usage than tree-based indexes; graph construction
is slower than ANNOY for initial builds.

**Use when**: the knowledge base is updated frequently (daily ingestion,
continuous document addition). HNSW's incremental insertion is the deciding
factor for dynamic corpora.

### Decision

| Corpus update frequency | Index choice |
|---|---|
| Infrequent (monthly or less) | ANNOY |
| Frequent (daily or continuous) | HNSW |

---

## Sparse Index: BM25

BM25 (Best Match 25) is the standard sparse retrieval scoring function. It
extends TF-IDF with two saturation parameters:

```
score(q, d) = Σ IDF(t) · (tf(t,d) · (k1 + 1)) / (tf(t,d) + k1 · (1 - b + b · |d|/avgdl))
```

Where:
- `tf(t,d)` — term frequency of term t in document d
- `IDF(t)` — inverse document frequency (penalizes common terms)
- `|d|` — document length; `avgdl` — average document length in corpus
- `k1` — term frequency saturation (typical: 1.2–2.0). Higher values give
  more weight to repeated terms; lower values saturate faster.
- `b` — document length normalization (typical: 0.75). `b=1` fully normalizes
  for length; `b=0` ignores length.

**Tuning**: default `k1=1.5, b=0.75` works well for most corpora. Increase
`k1` for corpora where term repetition is meaningful (legal documents);
decrease `b` for corpora with high natural length variance.

The sparse index is an inverted index: a mapping from each term to the list
of documents containing it, with BM25 scores precomputed or computed at query
time.

---

## Hybrid Fusion Mechanics

Hybrid retrieval produces two ranked lists — one from dense, one from sparse.
Fusion combines them into a single ranking.

### Reciprocal Rank Fusion (RRF)

```
RRF_score(d) = Σ_i  1 / (k + rank_i(d))
```

Where `rank_i(d)` is the rank of document d in retrieval system i, and `k`
is a smoothing constant (typically 60).

**Properties:**
- Works without score normalization — ranks are ordinal, not cardinal
- Robust to outliers: a document ranked 1st in one system and 100th in
  another still gets a reasonable combined score
- Insensitive to the absolute score scale of either retrieval system

**Use when**: the two retrievers produce scores on different scales (common),
or when you don't have calibrated confidence scores.

### Weighted Normalized Scores

Normalize each retriever's scores to [0, 1], then combine:

```
combined(d) = α · dense_score_norm(d) + (1 - α) · sparse_score_norm(d)
```

**Use when**: both retrievers are well-calibrated and you want explicit
control over the dense/sparse balance. Requires tuning `α` on a validation
set.

**Default recommendation**: RRF. It requires no calibration and performs
competitively across diverse corpora.

---

## Neural Reranking

A neural reranker (cross-encoder) takes a (query, document) pair as joint
input and produces a relevance score. Unlike embedding similarity, the
cross-encoder attends to both query and document simultaneously — capturing
fine-grained relevance signals that embedding-based retrieval misses.

**Architecture contrast:**

| | Bi-encoder (embedding) | Cross-encoder (reranker) |
|---|---|---|
| Input | Query and document encoded separately | Query + document encoded jointly |
| Speed | Fast — precompute document embeddings | Slow — must run inference per (query, doc) pair |
| Quality | Good for recall | Better for precision |
| Use | First-stage retrieval over full corpus | Second-stage reranking over top-k candidates |

**Practical pipeline:**

1. Retrieve top-50 to top-100 candidates via hybrid fusion
2. Rerank with cross-encoder → take top-5 to top-10 for injection

Running the reranker on the full corpus is prohibitively expensive. Always
apply it as a second-stage filter on the fusion output.

---

## Retrieval Quality Metrics

### recall@k

The fraction of relevant documents that appear in the top-k retrieved results.

```
recall@k = |relevant ∩ top-k| / |relevant|
```

Measures whether the retrieval system finds the right content at all.
Primary metric for first-stage retrieval. Target: recall@10 ≥ 0.85 before
optimizing precision.

### MRR (Mean Reciprocal Rank)

```
MRR = (1/|Q|) · Σ_q  1 / rank_q
```

Where `rank_q` is the rank of the first relevant document for query q.
Measures how far down the list the user must look to find the first relevant
result. Sensitive to whether the best result is ranked 1st vs 5th.

### nDCG (Normalized Discounted Cumulative Gain)

```
DCG@k = Σ_{i=1}^{k}  rel_i / log2(i + 1)
nDCG@k = DCG@k / IDCG@k
```

Where `rel_i` is the graded relevance of the document at rank i, and IDCG is
the ideal DCG (perfect ranking). Handles graded relevance — a highly relevant
document ranked 2nd is better than a marginally relevant document ranked 1st.

**When to use each:**

| Metric | Best for |
|---|---|
| recall@k | Evaluating first-stage retrieval coverage |
| MRR | Evaluating whether the best result is near the top |
| nDCG | Evaluating full ranking quality with graded relevance labels |

---

## Multimodal Extraction Paths

When the corpus contains images, tables, charts, or audio, three extraction
strategies apply:

| Strategy | How it works | Best for |
|---|---|---|
| **Native multimodal** | Vision encoder (ViT) + shared embedding space with text | Layout-sensitive content where spatial relationships matter (diagrams, forms, charts) |
| **Extract-to-text** | OCR for images/PDFs; ASR transcription for audio | Text-heavy documents where content is primarily textual; simpler pipeline |
| **Tool-based analysis** | On-demand analysis tool called by the agent | Rare or expensive content; when extraction quality must be verified per-query |

**Decision**:
- Layout-sensitive (spatial relationships carry meaning) → native multimodal
- Text-heavy (images are mostly text) → extract-to-text
- Low-frequency, high-value content → tool-based analysis

**Embedding alignment**: when mixing modalities, verify that text and image
embeddings are in the same vector space (contrastive training like CLIP).
Separate embedding spaces require separate indexes and fusion at the retrieval
layer.
