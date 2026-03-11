## 10. Reproducibility

### Environment setup

```bash
uv sync    # installs all dependencies from pyproject.toml
```

Key packages: pandas, numpy, scikit-learn, scipy, matplotlib, seaborn, sentence-transformers, torch (CPU-only, pinned via `[tool.uv.sources]`), networkx, python-louvain, hdbscan, umap-learn, adjustText, diptest (optional). Python >= 3.10.

### Script execution order

The pipeline has strict data dependencies. Scripts must be run in this order:

```bash
# Stage 1: Corpus construction (requires API access or local data)
uv run python scripts/catalog_istex.py              # parse ISTEX JSON
uv run python scripts/catalog_openalex.py            # query OpenAlex API (~15 min)
uv run python scripts/catalog_openalex_historical.py # historical works
uv run python scripts/catalog_bibcnrs.py             # parse bibCNRS RIS exports
uv run python scripts/catalog_scispsace.py           # parse SciSpace CSVs
uv run python scripts/catalog_grey.py                # World Bank API + YAML seeds

# Stage 2: Merge and refine
uv run python scripts/catalog_merge.py               # → unified_works.csv
uv run python scripts/corpus_refine.py --apply       # → refined_works.csv (22,113)

# Stage 3: Embeddings (~16 min full, incremental for additions)
uv run python scripts/analyze_embeddings.py          # → embeddings.npz (incremental cache)

# Stage 4: Co-citation (depends on citations.csv from enrich_citations.py)
uv run python scripts/analyze_cocitation.py          # → communities.csv

# Stage 5: Figures (each depends on refined_works.csv + embeddings.npz)
uv run python scripts/plot_fig1_emergence.py         # emergence
uv run python scripts/analyze_alluvial.py            # breakpoints + alluvial
uv run python scripts/analyze_alluvial.py --core-only   # core analysis
uv run python scripts/analyze_bimodality.py          # bimodality (must run before genealogy)
uv run python scripts/analyze_bimodality.py --core-only  # bimodality core variant
uv run python scripts/analyze_genealogy.py           # citation genealogy
uv run python scripts/plot_fig45_pca_scatter.py --core-only --supervised  # seed axis scatter (paper)
uv run python scripts/plot_fig45_pca_scatter.py      # unsupervised PCA scatter (appendix)

# Stage 6: Robustness appendices
uv run python scripts/analyze_alluvial.py --robustness   # k-sensitivity (k=4,5,6,7)
uv run python scripts/analyze_alluvial.py --core-only --censor-gap 1  # censored breaks
uv run python scripts/analyze_alluvial.py --core-only --censor-gap 2
uv run python scripts/analyze_alluvial.py --censor-gap 1
uv run python scripts/analyze_alluvial.py --censor-gap 2
uv run python scripts/analyze_genealogy.py --robustness  # Louvain resolution sensitivity
```

### Data dependencies

| Script | Reads | Writes |
|---|---|---|
| `catalog_merge.py` | `*_works.csv` | `unified_works.csv` |
| `corpus_refine.py` | `unified_works.csv`, `citations.csv`*, `embeddings.npz`* | `refined_works.csv`, `corpus_audit.csv` |
| `analyze_embeddings.py` | `refined_works.csv` | `embeddings.npz` (incremental cache), `semantic_clusters.csv` |
| `analyze_alluvial.py` | `refined_works.csv`, `embeddings.npz` | `fig_breakpoints`, `fig_composition`, `tab_*.csv`, `cluster_labels.json` |
| `analyze_bimodality.py` | `refined_works.csv`, `embeddings.npz` | `fig_bimodality*`, `tab_bimodality.csv`, `tab_pole_papers.csv`, `tab_axis_detection.csv` |
| `analyze_genealogy.py` | `refined_works.csv`, `citations.csv`, `semantic_clusters.csv`, `tab_pole_papers.csv` | `fig_genealogy`, `tab_lineages.csv` |
| `plot_fig45_pca_scatter.py` | `refined_works.csv`, `embeddings.npz` | `fig_seed_axis_core`, `fig_pca_scatter`, `tab_*.csv` |

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

### RePEc local mirror

The script `count_repec_econ_cf.py` reads from a local mirror of the RePEc ReDIF archives, providing an independent economics baseline for the emergence figure.

```bash
# Mirror setup (several GB, ~30 min)
mkdir -p ~/data/datasets/external/RePEc
rsync -va --delete rsync://rsync.repec.org/RePEc-ReDIF/ ~/data/datasets/external/RePEc/
```

The mirror was last synced 2026-02-26 (~2,334 archive directories). Re-run the same rsync command to update. Override the default path with `REPEC_ROOT` environment variable or `--repec-root` flag.

### Cross-machine reproducibility

Figures that do not involve KMeans clustering (fig_bars, fig_genealogy, fig_seed_axis_core, fig_robustness) are **byte-identical** across machines when `PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH=0` are set (the Makefile exports both).

Figures that depend on KMeans (fig_breakpoints, fig_composition, fig_bimodality, and their core variants) may differ across machines. This is because scikit-learn's KMeans delegates to platform-specific BLAS routines (OpenBLAS, MKL, Apple Accelerate), and floating-point summation order in distance computations is not guaranteed across implementations. The resulting cluster assignments can differ at the margin, producing visually similar but not byte-identical figures. Substantive results (breakpoint years, ΔBIC values, period boundaries) are robust to these differences.

### Non-reproducible steps

- ISTEX corpus download (requires institutional access)
- bibCNRS export (requires CNRS Janus credentials, manual browser export)
- Citation enrichment timing may vary due to Crossref index updates
- LLM audit (requires `OPENROUTER_API_KEY`; can be skipped with `--skip-llm`)
- RePEc mirror requires rsync access to `rsync.repec.org`

All scripts support a `--no-pdf` flag to skip PDF generation and produce PNG only.
