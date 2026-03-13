## 10. Reproducibility

### Environment setup

```bash
uv sync    # installs all dependencies from pyproject.toml
```

Key packages: pandas, numpy, scikit-learn, scipy, matplotlib, seaborn, sentence-transformers, torch (CPU-only, pinned via `[tool.uv.sources]`), networkx, python-louvain, hdbscan, umap-learn, adjustText, diptest (optional). Python >= 3.10.

### Script execution order

The pipeline has three phases. Use `make` to run them:

```bash
make corpus      # Phase 1: corpus building (slow — API calls, run rarely)
make figures     # Phase 2: analysis & figures (fast, deterministic)
make manuscript  # Phase 3: render PDF + DOCX
```

The Phase 1 → Phase 2 contract is three aligned files in `$CLIMATE_FINANCE_DATA/catalogs/`:
`refined_works.csv`, `refined_embeddings.npz`, `refined_citations.csv`.

`embeddings.npz` and `citations.csv` remain internal Phase 1 caches and are not
default Phase 2 inputs.

Phase 1 itself has five steps and four intermediate artifacts:

| Step | Make target | Reads | Writes |
|---|---|---|---|
| Discover | `corpus-discover` | source catalogs | `unified_works.csv` |
| Enrich | `corpus-enrich` | `unified_works.csv` | `enriched_works.csv` |
| Extend | `corpus-extend` | `enriched_works.csv` | `extended_works.csv` |
| Filter | `corpus-filter` | `extended_works.csv` | `refined_works.csv` |
| Align | `corpus-align` | `refined_works.csv`, `embeddings.npz`, `citations.csv` | `refined_embeddings.npz`, `refined_citations.csv` |

See `AGENTS.md` for individual script invocations and the `Makefile` for full dependency graph.

### Corpus validation and reporting

| Command | Purpose |
|---------|---------|
| `make corpus-validate` | Run acceptance checks (corpus size, flags, embeddings, citations, blacklist) |
| `make corpus-tables` | Regenerate per-source stats, citation coverage table, citation QC report |

| Script | Output | Used by |
|--------|--------|---------|
| `export_corpus_table.py` | `tab_corpus_sources.csv` | TechRep §1, Data Paper |
| `export_citation_coverage.py` | `tab_citation_coverage.md` | TechRep §10, Data Paper |
| `qc_citations.py` | `qc_citations_report.json` | TechRep §10 |

### Data dependencies

| Script | Reads | Writes |
|---|---|---|
| `catalog_merge.py` | `*_works.csv` | `unified_works.csv` |
| `enrich_dois.py` | `unified_works.csv` | `enriched_works.csv` |
| `enrich_abstracts.py` | `enriched_works.csv` | `enriched_works.csv` (in-place) |
| `enrich_citations_batch.py` | `enriched_works.csv` | `citations.csv` (append) |
| `enrich_citations_openalex.py` | `enriched_works.csv` | `citations.csv` (append) |
| `corpus_refine.py --extend` | `enriched_works.csv`, `citations.csv`*, `embeddings.npz`* | `extended_works.csv` |
| `corpus_refine.py --filter` | `extended_works.csv` | `refined_works.csv`, `corpus_audit.csv` |
| `analyze_embeddings.py` | `refined_works.csv` | `embeddings.npz` (incremental cache), `semantic_clusters.csv` |
| `compute_alluvial.py` | `refined_works.csv`, `refined_embeddings.npz` | `tab_alluvial.csv`, `tab_breakpoints.csv`, `tab_breakpoint_robustness.csv`, `cluster_labels.json`, `tab_core_shares.csv`, `tab_lexical_tfidf.csv` |
| `plot_fig_breakpoints.py` | `tab_breakpoints.csv`, `tab_breakpoint_robustness.csv`, `tab_alluvial.csv` | `fig_breakpoints.png` |
| `plot_fig_alluvial.py` | `tab_alluvial.csv`, `cluster_labels.json` | `fig_alluvial.png`, `fig_alluvial.html` |
| `analyze_bimodality.py` | `refined_works.csv`, `refined_embeddings.npz` | `fig_bimodality*`, `tab_bimodality.csv`, `tab_pole_papers.csv`, `tab_axis_detection.csv` |
| `analyze_genealogy.py` | `refined_works.csv`, `refined_citations.csv`, `semantic_clusters.csv`, `tab_pole_papers.csv` | `fig_genealogy`, `tab_lineages.csv` |
| `plot_fig45_pca_scatter.py` | `refined_works.csv`, `refined_embeddings.npz` | `fig_seed_axis_core`, `fig_pca_scatter`, `tab_*.csv` |

\* Optional; skipped with `--skip-citation-flag` or when file is absent.

### Data location

All generated data lives outside the repository at `~/data/projets/Oeconomia-Climate-finance/`. This path can be overridden by setting the `CLIMATE_FINANCE_DATA` environment variable. The `scripts/utils.py` module resolves `BASE_DIR` (repository root) and `CATALOGS_DIR` (catalogs/) for all scripts.

### Expected runtimes (CPU)

| Step | Time |
|---|---|
| OpenAlex harvest | ~15 min |
| Crossref citation enrichment | ~3--4 hours |
| Embedding generation | ~16 min full; incremental for additions |
| Breakpoint + alluvial analysis | ~2 min |
| Bimodality analysis | ~1 min |
| Citation genealogy | ~1 min |

### Cross-machine reproducibility

Figures that do not involve KMeans clustering (fig_bars, fig_genealogy, fig_seed_axis_core) are **byte-identical** across machines when `PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH=0` are set (the Makefile exports both).

Figures that depend on KMeans (fig_breakpoints, fig_composition, fig_bimodality, and their core variants) may differ across machines. This is because scikit-learn's KMeans delegates to platform-specific BLAS routines (OpenBLAS, MKL, Apple Accelerate), and floating-point summation order in distance computations is not guaranteed across implementations. The resulting cluster assignments can differ at the margin, producing visually similar but not byte-identical figures. Substantive results (breakpoint years, ΔBIC values, period boundaries) are robust to these differences.

### Non-reproducible steps

- ISTEX corpus download (requires institutional access)
- bibCNRS export (requires CNRS Janus credentials, manual browser export)
- Citation enrichment timing may vary due to Crossref index updates
- LLM audit (requires `OPENROUTER_API_KEY`; can be skipped with `--skip-llm`)
All scripts support a `--no-pdf` flag to skip PDF generation and produce PNG only.
