# Three lenses on a forming field: text, citations, and negotiation architecture in climate finance scholarship

## Research note — Ha-Duong

### Abstract (250 words)

How does the intellectual structure of a scholarly field relate to the political architecture it studies? We address this question for climate finance (1990–2024), a field that crystallized rapidly around the Copenhagen Accord (2009) and whose categories remain contested. Using a corpus of ~32,000 works, we compare three representations of the field's structure: semantic clusters derived from text embeddings (SPECTER2), communities derived from citation graph embeddings (node2vec), and the negotiation streams of the UNFCCC COP process (finance, mitigation, adaptation, loss & damage, markets, technology, transparency). The first two lenses are internal to the literature; the third is an external political classification that the field did not create but may have internalized.

The three-way comparison yields a diagnostic. Where text clusters align with citation communities, the field has coherent subfields. Where they diverge, we find thematic silos (same topic, no citation exchange) or citation bridges (different topics, shared lineage). Overlaying the COP negotiation rooms tests a sharper question: did climate finance scholars organize their intellectual work around the categories of the negotiations, or did they develop an autonomous structure? If academic clusters map onto COP rooms, the field adopted the policy architecture. If citation communities map better than text clusters, intellectual genealogy tracks the negotiations more closely than thematic similarity. If neither maps well, the field has structural autonomy from the process it studies.

We measure inter-cluster citation flows and their asymmetry across three periods, testing whether the field's internal hierarchy changed as it matured.

### Extended abstract

#### 1. Problem

Scientometric studies of field structure typically use either text-based methods (topic models, embedding clusters) or citation-based methods (co-citation, bibliographic coupling, community detection). Constantino et al. (2025, QSS) showed for physics that these two approaches capture complementary aspects of intellectual organization, with graph embeddings recovering formal disciplinary hierarchies better than text embeddings. But physics has a stable taxonomy (PACS codes) as ground truth. For forming fields, no such taxonomy exists.

Climate finance presents a distinctive variant of this problem. The field does not merely lack a disciplinary taxonomy — it has a *political* taxonomy imposed from outside: the UNFCCC negotiation architecture. COP sessions are structured into negotiation streams (finance, adaptation, mitigation, loss & damage, Article 6 markets, technology transfer, transparency), each with its own contact groups, submissions, and decision texts. These streams are political categories, not academic ones. But they may have structured academic attention: scholars who follow the finance negotiations may cite each other and use similar vocabulary, creating communities that mirror the COP architecture rather than any purely intellectual logic.

This gives us a third lens — and, critically, an external ground truth against which to evaluate the text and citation structures. The question is no longer just "do text and citations agree?" but "does the academic field mirror the policy process, and if so, through which channel — thematic imitation or citation networks?"

The three periods of climate finance — prehistory (1990–2006), crystallization (2007–2014), established field (2015–2024) — allow a temporal test. We expect the COP alignment to be weakest in period I (the field predates the negotiations' current structure) and strongest in period III (when the negotiations' categories are well-established and academic specialization has deepened).

#### 2. Data

The corpus comprises ~32,000 refined works from six sources (OpenAlex, ISTEX, bibCNRS, SciSpace, grey literature, teaching canon). Each work has:

- A SPECTER2 embedding (768 dimensions), enabling text-based clustering
- A position in the citation graph (~970,000 directed edges within the corpus), enabling graph-based community detection
- Metadata: publication year, cited_by_count, cluster assignment (k=6), period assignment

The COP negotiation structure is derived from UNFCCC documentation: the agenda items and negotiation streams of COP sessions from COP 1 (1995) to COP 29 (2024). Each stream is characterized by its key terms, decision texts, and institutional bodies (e.g., Standing Committee on Finance, Adaptation Committee, Article 6 Supervisory Body). We map corpus works to negotiation streams via keyword matching on titles and abstracts, using stream-specific vocabulary extracted from UNFCCC decision texts.

The core subset (~2,300 works cited ≥ 50 times) serves as a robustness check.

#### 3. Method

**Step 1 — Three partitions.** We produce three classifications of the corpus:
- *Text partition*: k-means on SPECTER2 embeddings (k=6, from the Oeconomia paper).
- *Graph partition*: node2vec embeddings (128 dimensions) on the citation graph, followed by Louvain community detection. We compare results at multiple resolutions to avoid dependence on a single granularity choice.
- *COP partition*: each work is assigned to zero, one, or more negotiation streams based on keyword matching. Works not assignable to any stream are labelled "outside COP architecture."

**Step 2 — Pairwise alignment.** For each pair of partitions, we compute adjusted Rand index (ARI) and normalized mutual information (NMI), globally and per period. This yields three alignment scores:
- Text ↔ Citation: do thematic neighbors cite each other?
- Text ↔ COP: does academic vocabulary track negotiation categories?
- Citation ↔ COP: do citation communities track negotiation categories?

The pattern of alignment scores is the main result. If Citation ↔ COP > Text ↔ COP, intellectual lineage tracks the negotiations more closely than thematic similarity — suggesting that the policy process structures *who reads whom* more than *what they write about*.

**Step 3 — Inter-cluster citation flows.** We compute the directed citation flow matrix between text clusters: what fraction of citations from cluster A go to cluster B? Asymmetry in this matrix reveals hierarchical relationships. We compute this matrix separately for each period, testing whether the hierarchy changes as the field matures. The hypothesis that requires falsification: if the flow matrix is stable across periods, the field's internal hierarchy was set early and did not change with the negotiations. If it shifts, the negotiations may have restructured intellectual attention.

**Step 4 — Silos and bridges.** Works where text cluster ≠ citation community are structurally interesting:
- *Silos*: same text cluster, different citation community — thematic proximity without intellectual exchange.
- *Bridges*: different text cluster, same citation community — citation links across thematic boundaries.

We characterize bridges: are they foundational texts that predate the field's differentiation, or are they recent works that actively connect traditions? The answer matters: old bridges suggest a shared origin, recent bridges suggest active integration.

#### 4. What would be genuinely surprising

The paper is interesting if at least one of these predictions fails:

- **COP alignment increases over time.** If it doesn't — if the field *diverges* from the negotiation architecture as it matures — that would mean scholars developed autonomous categories despite the political pressure to specialize along negotiation lines.

- **Citation communities track COP rooms better than text clusters do.** If the reverse holds — text clusters align better — it would mean thematic imitation dominates over social network effects, contradicting the Constantino et al. finding for physics.

- **Inter-cluster citation flows are asymmetric, with the "efficiency" pole receiving more citations.** If the flow is symmetric or reversed, the assumed hierarchy between technical and critical scholarship is not reflected in citation practice.

- **Bridges are old and foundational.** If bridges are recent, the field is actively integrating rather than passively inheriting connections from pre-differentiation ancestors.

#### 5. Contribution

1. **A three-lens protocol** for studying fields that exist at the science-policy interface. The COP partition provides an external benchmark that neither text nor citations can offer on their own. This is replicable for any field with a comparable institutional architecture (e.g., WHO for global health, OECD for development economics).

2. **An empirical characterization** of climate finance's intellectual structure that tests whether the field mirrors its policy object or has structural autonomy.

3. **An operational definition of field crystallization** as the progressive alignment of thematic proximity, citation practice, and external institutional categories — testable on other corpora.

#### 6. Target journal

Quantitative Science Studies or Scientometrics.

#### 7. Relation to other planned papers

- **Oeconomia paper** (submitted): provides the historical narrative and periodization.
- **Ravigné collaboration** (IPCC as category-maker): the IPCC is one institutional actor; the COP architecture is the broader political structure. This paper provides the baseline; the Ravigné paper tests one specific mechanism (IPCC citation selection).
- **Companion methods paper** (existing draft): focuses on temporal break detection and bimodality. This paper is about relational structure, not temporal dynamics.
