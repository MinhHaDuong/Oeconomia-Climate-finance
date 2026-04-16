---
paths:
  - "**/*"
---

# Architecture

## Project structure

Quarto multi-document project (`_quarto.yml`). Outputs share reusable fragments in `content/_includes/`:

- `content/manuscript.qmd` — main article (self-contained)
- `content/corpus-report.qmd` — corpus construction, data quality, corpus contents
- `content/technical-report.qmd` — analysis methods and results (composed of includes)
- `content/data-paper.qmd` — corpus data paper (RDJ4HSS submission)
- `content/companion-paper.qmd` — method paper (QSS submission, epic 0026)

## Pipeline phases

The pipeline has four phases. Each phase's scripts follow a naming convention and have clear input/output contracts. **Never let a later phase trigger an earlier one.**

**Phase 1 — Corpus building** (slow, API-dependent, run rarely on padme).
- Scripts: `catalog_*`, `enrich_*`, `qa_*`, `qc_*`, `corpus_*`
- Four steps with intermediate artifacts:
  1. **corpus-discover**: merge sources → `unified_works.csv`
  2. **corpus-enrich**: enrich DOIs/abstracts/citations → `enriched_works.csv`
  3. **corpus-extend**: flag all works (no rows removed) → `extended_works.csv`
  4. **corpus-filter**: apply policy, audit → `refined_works.csv`
- Phase 1 → Phase 2 **contract**: `refined_works.csv`, `refined_embeddings.npz`, `refined_citations.csv`

**Phase 2 — Analysis & figures** (fast, deterministic, run often):
- Scripts: `analyze_*`, `plot_*`, `compute_*`, `export_*`, `summarize_*`, `build_het_core.py`
- Reads Phase 1 outputs; produces `content/figures/`, `content/tables/`, `content/_includes/`, `content/*-vars.yml`

### Phase 2 rules

1. **1 invocation = 1 output.** Each Make target calls one script that writes one file. No side-effect outputs.
2. **Schema-validated.** New CSV artifacts get a Pandera schema in `scripts/schemas.py` (strict=True, coerce=True). Validate at write time — if the schema fails, the script fails, Make stops. (Legacy scripts are migrated as touched.)
3. **Modular Makefiles.** Each analysis concern gets its own `.mk` file (`divergence.mk`, etc.), included by the main Makefile. Adding a new analysis = adding a `.mk`, not editing a 400-line Makefile.
4. **Compute / Plot / Include are separate.** A compute script produces a table. A plot script reads a table and produces a figure. An include reads tables/figures and produces prose. Never mix.
5. **`save_figure()` mandatory.** All plot scripts use `save_figure(fig, stem, dpi=N)` from `pipeline_io.py` — strips metadata for byte-reproducible PNGs. Never call `fig.savefig()` directly.
6. **Config-driven parameters.** All research parameters in `config/analysis.yaml`, read via `load_analysis_config()`. No hardcoded constants for values that might change (windows, seeds, thresholds).
7. **Random seeds from config.** Every stochastic operation reads its seed from `config/analysis.yaml`. No hardcoded `seed=42` or `RandomState(42)`.
8. **Dispatcher pattern.** When multiple methods share data loading and output contract, use a single dispatch script with `--method X` (e.g., `compute_divergence.py`). Method implementations live in private modules (`_divergence_semantic.py`, etc.). Shared I/O helpers in `_divergence_io.py`.
9. **Corpus access through loaders only.** Never call `pd.read_csv()` / `np.load()` / `pd.read_feather()` on contract files (`refined_works`, `refined_embeddings`, `refined_citations`) directly. Use `pipeline_loaders`: `load_refined_works()` (thin read + type coercion), `load_analysis_corpus()` (filtered + optional embeddings), `load_refined_embeddings()`, `load_refined_citations()`. Direct reads bypass Feather acceleration, type coercion, and error hints — and create coupling points that break when the corpus format changes. (Legacy scripts are migrated as touched.)

**Phase 3 — Render** (Quarto → PDF/DOCX):
- Reads Phase 2 outputs. Build artifacts go to `output/` (gitignored).

**Phase 4 — Release & archives** (reproducibility packaging):
- Scripts: `release/scripts/build_*_archive.sh`
- Templates: `release/templates/` (Makefiles, READMEs, Dockerfiles shipped in archives)
- Reads Phase 2/3 outputs; produces `*.tar.gz` reproducibility archives

## Data location

Data lives **outside the repo**, at `CLIMATE_FINANCE_DATA` in `.env`.
`scripts/utils.py` reads `.env` and exports `DATA_DIR`, `CATALOGS_DIR`, `EMBEDDINGS_PATH`. Never hardcode `data/catalogs/` relative to the repo.

## Incremental caches vs DVC outputs

- **`enrich_cache/`** — persistent cache directory (gitignored, not a DVC output). Survives `dvc repro`.
- **DVC output** — declared in `dvc.yaml` `outs:`. Ephemeral — DVC may delete it.

When adding a new enrichment script: put incremental state in `enrich_cache/<name>.csv`, write the DVC output separately.
