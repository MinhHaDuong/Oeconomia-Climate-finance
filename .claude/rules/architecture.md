---
paths:
  - "scripts/**/*.py"
  - "tests/**/*.py"
  - "Makefile"
  - "dvc.yaml"
  - "config/**/*"
---

# Project Architecture

## Data location

Data lives **outside the repo**, at `CLIMATE_FINANCE_DATA` in `.env`.
`scripts/utils.py` reads `.env` and exports `DATA_DIR`, `CATALOGS_DIR`, `EMBEDDINGS_PATH`. Never hardcode `data/catalogs/` relative to the repo.

## Project structure

Quarto multi-document project (`_quarto.yml`). Four outputs share reusable fragments in `content/_includes/`:

- `content/manuscript.qmd` — main article (self-contained)
- `technical-report.qmd` — pipeline documentation (composed of includes)
- `data-paper.qmd` — corpus data paper
- `companion-paper.qmd` — methods companion

## Pipeline phases

**Phase 1 — Corpus building** (slow, API-dependent, run rarely).
- Scripts: `catalog_*`, `enrich_*`, `qa_*`, `qc_*`, `corpus_*`
- Four steps with intermediate artifacts:
  1. **corpus-discover**: merge sources → `unified_works.csv`
  2. **corpus-enrich**: enrich DOIs/abstracts/citations → `enriched_works.csv`
  3. **corpus-extend**: flag all works (no rows removed) → `extended_works.csv`
  4. **corpus-filter**: apply policy, audit → `refined_works.csv`
- Phase 1 → Phase 2 **contract**: `refined_works.csv`, `embeddings.npz`, `citations.csv`

**Phase 2 — Analysis & figures** (fast, deterministic, run often):
- Scripts: `analyze_*`, `plot_*`, `compute_*`, `export_*`, `summarize_*`, `build_het_core.py`
- Reads Phase 1 outputs; produces `content/figures/`, `content/tables/`, `content/_includes/`, `content/*-vars.yml`

**Phase 3 — Render** (Quarto → PDF/DOCX):
- Reads Phase 2 outputs. Build artifacts go to `output/` (gitignored).

**Phase 4 — Release & archives** (reproducibility packaging):
- Scripts: `release/scripts/build_*_archive.sh`
- Templates: `release/templates/` (Makefiles, READMEs, Dockerfiles shipped in archives)
- Reads Phase 2/3 outputs; produces `*.tar.gz` reproducibility archives

## Incremental caches vs DVC outputs

- **`enrich_cache/`** — persistent cache directory (gitignored, not a DVC output). Survives `dvc repro`.
- **DVC output** — declared in `dvc.yaml` `outs:`. Ephemeral — DVC may delete it.

When adding a new enrichment script: put incremental state in `enrich_cache/<name>.csv`, write the DVC output separately.
