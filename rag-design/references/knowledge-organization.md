# Knowledge Organization

*Synthesized from [AI Agents in Depth (Bojie Li, v1.2)](https://github.com/bojieli/ai-agent-book/blob/main/book-en/AI-Agents-in-Depth-Bojie-Li-v1.2.pdf) — full chapter map in [docs/sources/ai-agents-bojie-li.md](../../docs/sources/ai-agents-bojie-li.md).*

---

## RAPTOR Tree Construction

RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval) builds
a hierarchical index through bottom-up recursive summarization.

### Construction pipeline

1. **Chunk** documents at leaf level (standard chunking from §1)
2. **Embed** all leaf chunks
3. **Cluster** leaf chunks by embedding similarity
   - Gaussian Mixture Models (GMM): soft clustering — a chunk can belong to
     multiple clusters with different probabilities. Handles overlapping
     concepts well.
   - k-means: hard clustering — simpler, faster, sufficient when concepts are
     distinct.
4. **Summarize** each cluster with an LLM → produces a parent node
5. **Repeat** steps 2–4 on the parent nodes until a single root summary

The result is a tree where leaves are raw chunks, intermediate nodes are
cluster summaries, and the root is a document-level (or corpus-level) summary.

### Query routing

At query time, match against nodes at multiple granularities simultaneously:

- **Root and upper layers**: catch broad conceptual queries ("what is this
  document about?")
- **Leaf layer**: catch specific factual queries ("what was revenue in Q2?")
- **Intermediate layers**: catch mid-level queries ("summarize the financial
  performance section")

RAPTOR does not require choosing a single granularity — retrieve candidates
from all layers, then rerank.

### When to use

RAPTOR excels at "drill from concept to details" navigation. It is less
suited to entity-relationship queries where the structure is a graph, not a
hierarchy.

---

## GraphRAG

GraphRAG constructs a knowledge graph from the corpus, enabling multi-hop
relational reasoning that flat retrieval cannot support.

### Construction pipeline

1. **Entity extraction**: identify named entities (people, organizations,
   products, concepts) in each document chunk
2. **Relationship extraction**: identify relationships between entities
   ("ACME acquired Globex in 2023")
3. **Graph construction**: nodes = entities; edges = relationships with
   attributes (relationship type, source document, confidence)
4. **Community detection**: cluster the graph into communities of closely
   related entities (Leiden algorithm or similar)
5. **Community summaries**: LLM generates a summary for each community,
   capturing the key entities and relationships within it

### Query routing

- **Local search**: start from a seed entity, traverse edges to find related
  entities and their relationships. Best for "tell me about X and its
  connections."
- **Global search**: use community summaries to answer broad thematic queries
  without traversing the full graph.

### Strengths

- Multi-hop reasoning: "find all companies that acquired a competitor in 2023,
  then find their CEOs" — requires traversing multiple edges
- Entity disambiguation: the same entity name in different documents is
  resolved to a single node
- Cross-document synthesis: relationships extracted from different documents
  are unified in the graph

### Weaknesses

Converting natural language to triples is lossy:

- **Conditional logic**: "revenue grew 3% unless adjusted for currency
  effects" → triples cannot represent the conditional
- **Temporal dependencies**: "the policy changed in Q3" → requires temporal
  edge attributes that are often dropped
- **Hedged statements**: "analysts believe X may acquire Y" → confidence and
  modality are lost in extraction

GraphRAG excels at "who is connected to whom" queries. It struggles with
"what changed between periods" or "under what conditions does X apply."

---

## Filesystem Paradigm (L0/L1/L2)

Three-layer progressive disclosure for structured document corpora. Each
layer serves a different retrieval granularity.

### Layer structure

| Layer | Content | Purpose |
|---|---|---|
| **L0** | Directory index — one-line summaries of each document or section | Fast orientation; agent discovers what exists |
| **L1** | Section overviews — paragraph-length summaries | Mid-level navigation; agent identifies relevant sections |
| **L2** | Full content | Detailed retrieval; agent reads specific passages |

### Critical requirement: cross-references

Links between files are not optional. Without them, retrieval decays into
disconnected islands — the agent finds a document but cannot navigate to
related content. Every L0 entry should link to its L1; every L1 section
should link to its L2 content and to related L0 entries.

**Anti-pattern**: a flat directory of documents with no cross-references.
The agent can find individual documents but cannot discover that "the
authentication policy" is related to "the session management guide."

### Reference architecture

The `knowledge-base` skill's MOC (Map of Content) structure is an instance
of this paradigm: the INDEX.md is L0, individual MOC files are L1, and
atomic notes are L2. The wikilink graph provides the cross-references.

### When to use

Best for corpora with natural hierarchical or categorical structure:
documentation sets, policy libraries, research archives. Less suited to
unstructured document collections where hierarchy must be imposed artificially.

---

## Knowledge Governance

A retrieval system that isn't maintained degrades. Governance covers
staleness detection, incremental updates, multi-user access, and versioning.

### Staleness detection

Documents have implicit or explicit expiration:

- **Explicit**: documents with "valid until" dates, versioned policies,
  time-bounded reports
- **Implicit**: any document referencing current state (prices, personnel,
  system configurations) that hasn't been updated in a defined period

Governance requires a staleness signal: either metadata-driven (last-updated
timestamp + TTL) or content-driven (LLM-based freshness classification).
Stale documents should be flagged for review or removed from the index rather
than silently served.

### Incremental updates

| Index type | Incremental support |
|---|---|
| HNSW | Supports incremental insertion — add new documents without rebuilding |
| ANNOY | Does not support incremental insertion — requires full rebuild |
| Inverted index (BM25) | Supports incremental updates with standard IR techniques |

For dynamic corpora, HNSW is the correct dense index choice (see
`retrieval-infrastructure.md`). Pair with an incremental BM25 implementation
for the sparse component.

**Deletion**: removing documents from HNSW requires marking nodes as deleted
(lazy deletion) and periodic graph compaction. Track document IDs in a
metadata store to support deletion by document reference.

### Multi-user sharing

When multiple users share a knowledge base with different access permissions:

- **Permission filtering at retrieval layer**: retrieve candidates broadly,
  then filter by the requesting user's permissions before returning results.
  Never embed permission checks inside the index — indexes don't understand
  permissions.
- **Tenant isolation**: for strict isolation requirements, maintain separate
  indexes per tenant. Simpler to reason about; higher infrastructure cost.
- **Namespace partitioning**: a middle ground — shared index with namespace
  prefixes on document IDs, filtered at query time. Works when tenants have
  non-overlapping document sets.

### Content versioning

When documents are updated, the old version's chunks remain in the index
until explicitly removed. Without versioning:

- Queries may return outdated information alongside current information
- Contradictions appear when old and new versions of a policy coexist

Versioning strategy: tag each chunk with a document version and timestamp.
At query time, filter to the latest version of each document. Retain old
versions for audit purposes but exclude them from default retrieval.

---

## Deep Knowledge Extraction

For structured data sources (databases, spreadsheets, financial reports),
raw text chunking loses the relational structure. Deep knowledge extraction
preserves it.

### Pipeline

1. **LLM-driven factor discovery**: given a structured data source, use an
   LLM to identify the key factors or dimensions that characterize the data
   (e.g., for a financial dataset: revenue, margin, growth rate, segment)
2. **Modular schema construction**: define a schema capturing those factors
   as typed fields
3. **Feature vectorization**: convert each record's factor values into a
   feature vector (numerical encoding, normalization)
4. **Clustering**: group records by feature similarity to discover natural
   categories
5. **Importance modeling**: weight factors by their discriminative power
   across clusters

### Application: guided question generation

An agent equipped with a deep knowledge index can guide its own retrieval
by factor importance — asking about high-importance factors first, then
drilling into lower-importance factors for records that match. This produces
more efficient multi-turn retrieval than open-ended search.

**Example**: a financial analysis agent with a deep knowledge index of
company reports asks about revenue growth (high importance) before asking
about footnote disclosures (low importance), and skips low-importance factors
for companies that don't match the initial criteria.

### When to use

Deep knowledge extraction is justified when:
- The corpus is structured (tables, records, financial statements)
- Queries require comparison across multiple records
- The agent needs to prioritize which aspects to investigate

For unstructured text corpora, standard chunking + hybrid retrieval (§2) is
sufficient.
