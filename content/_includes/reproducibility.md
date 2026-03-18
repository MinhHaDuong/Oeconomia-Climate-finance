## 12. Reproducibility

### Environment setup

```bash
uv sync    # installs all dependencies from pyproject.toml
```

Key packages: pandas, numpy, scikit-learn, scipy, matplotlib, seaborn, sentence-transformers, torch (CPU or CUDA, selected via `--extra cpu` or `--extra cu130`), networkx, python-louvain, hdbscan, umap-learn, adjustText, diptest (optional). Python >= 3.10.

### Execution

The pipeline has three phases. Use `make` to run them:

```bash
make corpus      # Phase 1: corpus building (slow — API calls, run rarely)
make figures     # Phase 2: analysis & figures (fast, deterministic)
make manuscript  # Phase 3: render PDF + DOCX
```

The Phase 1 to Phase 2 contract is three aligned files in `$CLIMATE_FINANCE_DATA/catalogs/`: `refined_works.csv`, `refined_embeddings.npz`, `refined_citations.csv`. The intermediate artifacts are `unified_works.csv` (discover), `enriched_works.csv` (enrich), and `extended_works.csv` (extend). The refine step uses `corpus_refine.py` in two modes: `--extend` to compute quality flags on all works (producing `extended_works.csv`), then `--filter` to apply the retention policy (producing `refined_works.csv` and `corpus_audit.csv`). Full details of each step are in Part I (§§1--3); Phase 2 script inputs and outputs are in each analysis section (§§5--11).

See the `Makefile` for the full dependency graph and `dvc.yaml` for the DVC pipeline stages.

![DVC pipeline DAG — generated from `dvc.yaml` by `scripts/plot_fig_dag.py`.](figures/fig_dag.png){#fig-dag width=100%}

### Validation

| Command | Purpose |
|---------|---------|
| `make corpus-validate` | Run acceptance checks (corpus size, flags, embeddings, citations, blacklist) |
| `make corpus-tables` | Regenerate per-source stats, citation coverage table, citation QC report |

| Script | Output | Used by |
|--------|--------|---------|
| `export_corpus_table.py` | `tab_corpus_sources.csv` | TechRep §1, Data Paper |
| `export_citation_coverage.py` | `tab_citation_coverage.md` | TechRep §11, Data Paper |
| `qa_citations.py` | `qa_citations_report.json` | TechRep §11 |

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

Figures and tables are **byte-identical** across machines when `PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH=0` are set (the Makefile exports both).

scikit-learn's KMeans delegates to platform-specific BLAS routines (OpenBLAS, MKL, Apple Accelerate), and floating-point summation order in distance computations is not guaranteed across implementations. To absorb this jitter, all CSV outputs are rounded to bounded precision: BIC values to integers, correlations and variance ratios to 4 decimal places, per-paper axis scores to 4 decimal places. At this precision, outputs are identical across tested platforms (Intel MKL on x86, OpenBLAS on x86 with NVIDIA GPU).

### Non-reproducible steps

- ISTEX corpus download (requires institutional access)
- bibCNRS export (requires CNRS Janus credentials, manual browser export)
- Citation enrichment timing may vary due to Crossref index updates
- LLM audit (requires `OPENROUTER_API_KEY`; can be skipped with `--skip-llm`)

All scripts support a `--no-pdf` flag to skip PDF generation and produce PNG only.
