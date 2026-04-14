## Cross-encoder Calibration {#sec-reranker-calibration}

Flag 6 uses a cross-encoder reranker rather than a generative LLM to classify papers as relevant or irrelevant. Cross-encoders score a (query, document) pair by jointly encoding both through a transformer, producing a single relevance score. This is deterministic, reproducible, and runs locally on CPU without API costs.

**Model.** We use `BAAI/bge-reranker-v2-m3` (568M parameters, multilingual), loaded via the `sentence-transformers` `CrossEncoder` class. The model scores each candidate paper's title and abstract against a query string, producing a continuous relevance score. Scores are cached per DOI so that threshold adjustments do not require re-scoring.

**Query optimization.** The query string determines what the cross-encoder considers "relevant." Rather than choosing a query by hand, we searched systematically across 100 candidate queries generated from:

- 5 domain templates (e.g., "history of economic thought on climate finance," "climate finance measurement and accounting")
- 5 topic templates (e.g., "climate policy and financial mechanisms," "carbon markets and environmental finance")
- 4 syntactic variations per template (bare, with "Relevance for" prefix, with appended subtopics)
- 66 two-term combinations drawn from 12 core terms (climate finance, carbon market, green bond, adaptation finance, etc.)
- 3 hand-crafted scholarly queries

Each candidate query was evaluated on a stratified sample of 200 papers (100 positive, 100 negative) drawn from weak labels, ranked by AUC (area under the ROC curve, computed via Mann-Whitney U statistic).

**Weak labels.** To avoid circular validation against LLM outputs, we built weak labels from independent corpus signals:

- *Positive set* (~2,356 papers): papers appearing in teaching syllabi, cited 50+ times (`cited_by_count`), or discovered by 3+ independent sources (`source_count`).
- *Negative set* (~1,174 papers): papers flagged by Flags 1--3 (missing metadata, no abstract with irrelevant title, or title blacklist match), excluding any overlap with the positive set.

**Results.** The best query was "climate policy and financial mechanisms" (AUC = 0.766). The top 5 queries clustered tightly (AUC 0.75--0.77), suggesting the model's discriminative power is stable across reasonable query formulations. The bottom queries involved narrow institutional terms ("UNFCCC, Paris Agreement," AUC = 0.53), confirming that overly specific queries lose generality.

**Threshold selection.** Using the best query, all 3,530 labeled papers were scored. Score distributions are compressed near zero (positive mean = 0.032, negative mean = 0.006). An initial threshold of 0.0049 was selected via Youden's J on weak labels. This was then validated and adjusted through human-in-the-loop review.

**Human validation.** A stratified sample of 100 papers (20 per score quintile) was presented in randomized order, blinded to scores and metadata, for human labeling against the criterion: "Is this paper relevant to the history of economic thought on climate finance?" The AUC against human labels was 0.818, higher than the 0.766 against weak labels, confirming the reranker's discriminative power. The proportion of human-relevant papers increased monotonically across score quintiles (10%, 15%, 20%, 60%, 80%), showing a clear signal. However, the initial threshold of 0.0049 fell in a zone where 60% of papers were human-relevant, indicating excessive removal. The threshold was adjusted to 0.002, yielding 81% accuracy (precision = 74%, recall = 76%) on the human-labeled sample. At this threshold, strata 1--3 (scores below 0.002, where 85% of papers are irrelevant) are removed, while strata 4--5 (where 60--80% are relevant) are retained.

**Comparison with LLM backend.** The cross-encoder replaces the previous Gemini Flash (OpenRouter) / Qwen 32B (Ollama) backend. Advantages: deterministic output, no API dependency, ~5 minutes on 24 CPU threads vs. ~15 minutes with rate-limited API calls, zero marginal cost. The continuous score also enables threshold tuning without re-running the model.
