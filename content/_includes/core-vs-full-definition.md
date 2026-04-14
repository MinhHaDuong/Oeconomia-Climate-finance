## Core vs. Full Corpus

The pipeline implements a two-level analytical design:

### Full corpus ({{< meta corpus_with_embeddings >}} papers with embeddings)

The broad field of "scholarship around climate finance." This includes not only specialized climate finance papers but also adjacent work in environmental economics, green finance, energy policy, and development economics. The full corpus captures the field's periphery and the volume of new entrants over time.

### Core subset (~{{< meta corpus_core >}} papers, cited_by_count >= {{< meta corpus_core_threshold >}})

The influential intellectual core. These are the papers that have shaped the field's concepts, debates, and categories. The core subset is analyzed separately by passing `--core-only` to `compute_clusters.py` and the corresponding plotting scripts.
