## 13. Reproducibility

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

The Phase 1 to Phase 2 contract is three aligned files in `$CLIMATE_FINANCE_DATA/catalogs/`: `refined_works.csv`, `refined_embeddings.npz`, `refined_citations.csv`. The intermediate artifacts are `unified_works.csv` (discover), `enriched_works.csv` (enrich), and `extended_works.csv` (extend). The filter step uses `corpus_filter.py` in two modes: `--extend` to compute quality flags on all works (producing `extended_works.csv`), then `--filter` to apply the retention policy (producing `refined_works.csv` and `corpus_audit.csv`). Full details of each step are in Part I (§§1--3); Phase 2 script inputs and outputs are in each analysis section (§§5--11).

See the `Makefile` for the full dependency graph and `dvc.yaml` for the DVC pipeline stages.

![DVC pipeline DAG — generated from `dvc.yaml` by `scripts/plot_fig_dag.py`.](figures/fig_dag.png){#fig-dag width=100%}

### Validation

| Command | Purpose |
|---------|---------|
| `make corpus-validate` | Run acceptance checks (corpus size, flags, embeddings, citations, blacklist) |
| `make corpus-tables` | Regenerate per-source stats, citation coverage table, citation QC report |

| Script | Output | Used by |
|--------|--------|---------|
| `export_corpus_table.py` | `tab_corpus_sources.csv`, `tab_corpus_sources.md` | TechRep §1, Data Paper |
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

### Performance: DataFrame library and storage format

We benchmarked alternative DataFrame libraries and storage formats on the actual pipeline data (31,713 refined works, 835,455 citations) to evaluate potential speedups. All timings are medians over 3--5 runs after a warmup pass, on a single machine (Intel x86, SSD).

**DataFrame library.** Polars 1.39 vs pandas 2.2, reading from CSV:

| Operation | pandas | Polars | Speedup |
|---|---|---|---|
| CSV read refined works | 0.54 s | 0.11 s | 5× |
| CSV read citations | 2.87 s | 0.09 s | 33× |
| GroupBy aggregation | 0.04 s | 0.02 s | 2× |
| Left join | 6 ms | 2 ms | 3× |
| String filter | 24 ms | 7 ms | 3× |
| Sort | 8 ms | 2 ms | 3× |
| CSV write | 0.70 s | 0.04 s | 17× |

Polars is 3--33× faster on I/O and 2--3× faster on in-memory operations. However, migrating 108 Python files to Polars' incompatible API would require rewriting every call site plus conversion shims at every scikit-learn, matplotlib, and numpy boundary. We retain pandas.

**Storage format.** We then tested pandas' pyarrow CSV engine, Parquet, and Feather (Arrow IPC) against the default C-engine CSV reader:

| Format | refined_works (31K rows) | citations (835K rows) | Disk size (works / citations) |
|---|---|---|---|
| CSV (default C engine) | 0.65 s | 4.16 s | 62 / 317 MB |
| CSV (pyarrow engine) | fails^[The `refined_works.csv` abstract column contains embedded newlines inside quoted fields. The pyarrow CSV parser rejects these, while the default C parser handles them. Fixing this would require sanitizing all abstract text at write time.] | 0.09 s | --- |
| Parquet | 0.13 s | 0.58 s | 30 / 122 MB |
| Feather (Arrow IPC) | 0.03 s | 0.08 s | 31 / 135 MB |

Feather is 20--50× faster than CSV, and both binary formats halve disk usage through columnar compression. The pyarrow CSV engine, which would have been a zero-migration speedup, fails on the works file due to embedded newlines in abstracts.

**Cumulative cost.** The CSV parse cost is paid independently by each script: 16 Phase 2 scripts read `refined_works.csv` and 9 read `refined_citations.csv`, with no cross-script caching. A full `make analysis-figures` run thus spends ~0.65 s × 16 + ~4.2 s × 9 ≈ 48 seconds on CSV parsing alone. With Feather this drops to ~1.5 seconds.

**Implementation.** CSV remains the canonical archival format — human-readable, diff-friendly, and shipped in reproducibility archives. An optional `make corpus-handoff` step converts CSV to Feather for developers iterating on Phase 2 scripts. The Phase 2 loaders (`pipeline_loaders.py`) prefer Feather when present and fall back to CSV transparently.

### Cross-machine reproducibility

Figures and tables are **byte-identical** across machines when `PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH=0` are set (the Makefile exports both).

scikit-learn's KMeans delegates to platform-specific BLAS routines (OpenBLAS, MKL, Apple Accelerate), and floating-point summation order in distance computations is not guaranteed across implementations. To absorb this jitter, all CSV outputs are rounded to bounded precision: BIC values to integers, correlations and variance ratios to 4 decimal places, per-paper axis scores to 4 decimal places. At this precision, outputs are identical across tested platforms (Intel MKL on x86, OpenBLAS on x86 with NVIDIA GPU).

### Non-reproducible steps

- ISTEX corpus download (requires institutional access)
- bibCNRS export (requires CNRS Janus credentials, manual browser export)
- Citation enrichment timing may vary due to Crossref index updates
- LLM audit (requires `OPENROUTER_API_KEY`; can be skipped with `--skip-llm`)

All plot scripts produce PNG by default; pass `--pdf` for print-quality PDF output.
