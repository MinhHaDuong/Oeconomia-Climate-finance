## 4. Core vs. Full Corpus Analysis

The pipeline implements a two-level analytical design:

### Full corpus ({{< var corpus_with_embeddings >}} papers with embeddings)

The broad landscape of "scholarship around climate finance." This includes not only specialized climate finance papers but also adjacent work in environmental economics, green finance, energy policy, and development economics. The full corpus captures the field's periphery and the volume of new entrants over time.

### Core subset (~{{< var corpus_core >}} papers, cited_by_count >= {{< var corpus_core_threshold >}})

The influential intellectual core. These are the papers that have shaped the field's concepts, debates, and categories. The core subset is analyzed separately by passing `--core-only` to `compute_alluvial.py` and the corresponding plotting scripts.

### Key differences

- **Breakpoints:** The full corpus shows structural breaks at 2007 and 2013. The core subset shows no break in the 2007--2015 range; its only detected break is at 2023 (likely an edge effect). This indicates that structural shifts in the full corpus are driven by the influx of new scholarship, not by changes in the core community's thematic composition.
- **Alluvial:** The core alluvial shows a more stable thematic structure across periods, while the full-corpus alluvial captures the growth of new thematic clusters (e.g., green bonds, ESG).
- **Clustering:** KMeans is re-fitted on core embeddings independently (not inherited from the full corpus), with min_df=3 and N_MIN=20 to accommodate the smaller sample.
- **Bimodality:** The efficiency↔accountability divide is present in both samples but manifests differently. Full corpus: ΔBIC = {{< var bim_dbic_embedding >}} (strong). Core: ΔBIC = {{< var bim_core_dbic_embedding >}} (embedding), {{< var bim_core_dbic_tfidf >}} (TF-IDF). The lexical signal is stronger in core because influential papers use more distinctive vocabulary; the embedding signal is weaker because the core is more thematically coherent.
- **Unsupervised PCA bimodality:** Three PCs show bimodality (ΔBIC > 200) in the full corpus; none do in the core. The unsupervised discovery of bimodal axes requires the full corpus's breadth. The supervised seed axis remains bimodal in core, confirming that the divide is real but not dominant enough to emerge unsupervised from only {{< var corpus_core >}} papers.

### Rationale

The two-level design disentangles two dynamics: (1) the diversification of the broader literature, visible in the full corpus, and (2) the consolidation of the intellectual core, visible in the core subset. Their divergence supports the article's argument that the field's foundational categories crystallized early and have remained stable even as the volume of surrounding literature has grown.
