# Coding Guidelines

Consult this file when writing or modifying Python scripts, pipeline steps, or build targets.

## Testing

- Tests live in `tests/`. A new script or changed behavior starts with a test in `tests/test_<module>.py`.
- `make check-fast`: unit tests + prose lint, <30 s — run during development.
- `make check`: full suite including slow tests — run before opening a PR.
- Acceptance tests (e.g., `make corpus-validate`) are the top-level contract — never weaken them without discussion.

## Conventions

- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- All scripts support `--no-pdf`.
- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companion documents. `make figures` regenerates all figures (byte-reproducible).
- House style: `docs/oeconomia-style.md` (eyeballed from 15-4 samples)
- **Logging, not print.** All scripts MUST use `from utils import get_logger; log = get_logger("script_name")` — never bare `print()`. The `get_logger()` factory configures a shared `pipeline` root logger with `StreamHandler` (auto-flush to stderr, `HH:MM:SS LEVEL message` format). Use `log.info()` for progress, `log.warning()` for retries/rate-limits, `log.error()` for failures.

## Dependency management

- **Always use `uv sync`** to install dependencies. Never use `pip` or `uv pip`.
- All dependencies are declared in `pyproject.toml` at project root.
- torch is installed via mutually exclusive extras: `--extra cpu` (doudou) or `--extra cu130` (padme, CUDA 13.0). Scripts auto-detect GPU via `torch.cuda.is_available()`.
- To add a dependency: edit `pyproject.toml`, then run `uv sync`.

## Data location

- Data lives **outside the repo**, at the path set by `CLIMATE_FINANCE_DATA` in `.env`.
- `scripts/utils.py` reads `.env` and exports `DATA_DIR`, `CATALOGS_DIR`, `EMBEDDINGS_PATH`. Never hardcode `data/catalogs/` relative to the repo — it doesn't exist there.

## Project structure

Quarto multi-document project (`_quarto.yml`). Four outputs share reusable fragments in `content/_includes/` via `{{< include >}}` directives:

- `content/manuscript.qmd` — main Œconomia article (self-contained, no includes)
- `technical-report.qmd` — pipeline documentation (composed entirely of includes)
- `data-paper.qmd` — corpus data paper (reuses corpus-construction + reproducibility)
- `companion-paper.qmd` — methods companion (reuses all analysis sections)

### File management
- Working drafts: Quarto Markdown (`.qmd`); final submission: PDF or DOCX
- Build with `make` (calls `quarto render` under the hood)
- Shared fragments live in `content/_includes/` — edit there, all documents update
- Bibliography: `content/bibliography/main.bib`, author-date style
- Version control: old versions in `attic/`, submissions in `release/`

## Pipeline phases

The pipeline has three phases with a strict contract between them:

**Phase 1 — Corpus building** (slow, API-dependent, run rarely).
Phase 1 modifies `data/`. Run only when explicitly requested.
- Scripts: `catalog_*`, `enrich_*`, `qa_*`, `qc_*`, `corpus_*`
- Four steps with intermediate artifacts in `data//catalogs/`:
  1. **corpus-discover**: merge sources → `unified_works.csv`
  2. **corpus-enrich**: enrich DOIs/abstracts/citations on `unified_works.csv` → `enriched_works.csv`
  3. **corpus-extend**: flag all works (no rows removed) → `extended_works.csv`
  4. **corpus-filter**: apply policy, audit → `refined_works.csv` (final Phase 1 output)
- Phase 1 → Phase 2 **contract**: `refined_works.csv`, `embeddings.npz`, `citations.csv`
- Run with: `make corpus` (all four steps) or individual targets
- Validate: `make corpus-validate` (44-check acceptance test)
- Report: `make corpus-tables` (per-source stats, citation coverage, QC report)

**Phase 2 — Analysis & figures** (fast, deterministic, run often):
- Scripts: `analyze_*`, `plot_*`, `compute_*`, `export_*`, `summarize_*`, `build_het_core.py`
- Reads ONLY Phase 1 outputs; produces `content/figures/`, `content/tables/`, `content/_includes/`, `content/*-vars.yml`
- Phase 2 → Phase 3 **contract**: all Phase 2 outputs are **git-tracked** so Phase 3 can build without rerunning Phase 2. After a corpus regen, commit updated figures/tables before rendering.
- Run with: `make figures`

**Phase 3 — Render** (Quarto → PDF/DOCX):
- Reads ONLY git-tracked Phase 2 outputs. Build artifacts go to `output/` (gitignored).
- Run with: `make manuscript` or `make papers`

**Versioning policy:**
| Phase | Artifacts | Versioned by |
|-------|-----------|-------------|
| 1 | `data/catalogs/` | DVC |
| 2 | `content/figures/`, `content/tables/`, `content/_includes/`, `content/*-vars.yml` | gitignored (like figures) |
| 3 | `output/` | not tracked (gitignored) |

## Script reference

```bash
# Citation enrichment (run in order; both are resumable)
uv run python scripts/enrich_citations_batch.py                  # Crossref references (do first)
uv run python scripts/enrich_citations_openalex.py               # OpenAlex referenced_works (fills gap)
uv run python scripts/qa_citations.py                            # Verify citation quality (30-sample)
# Or simply: make citations  (runs all three in order)

# Figures — alluvial pipeline (split into focused scripts as of #73)
uv run python scripts/compute_breakpoints.py     # tab_breakpoints.csv, tab_breakpoint_robustness.csv
uv run python scripts/compute_clusters.py        # tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv
uv run python scripts/compute_lexical.py         # tab_lexical_tfidf.csv (all breaks + controls, with p-values)
uv run python scripts/plot_fig_breakpoints.py    # fig_breakpoints.png
uv run python scripts/plot_fig_alluvial.py       # fig_alluvial.png + .html
uv run python scripts/compute_breakpoints.py --core-only       # Core variants of breakpoints tables
uv run python scripts/compute_clusters.py --core-only          # Core variants of alluvial tables
uv run python scripts/plot_fig_breakpoints.py --core-only      # fig_breakpoints_core.png
uv run python scripts/plot_fig_alluvial.py --core-only         # fig_alluvial_core.png
uv run python scripts/compute_breakpoints.py --robustness      # tab_k_sensitivity.csv
uv run python scripts/plot_fig_k_sensitivity.py                # fig_k_sensitivity.png
uv run python scripts/plot_fig_lexical_tfidf.py                # fig_lexical_tfidf_{year}.png per break
uv run python scripts/compute_breakpoints.py --censor-gap 1    # Censored breaks (k=1)
uv run python scripts/compute_breakpoints.py --censor-gap 2    # Censored breaks (k=2)
uv run python scripts/analyze_bimodality.py      # Fig 5a/5b/5c
uv run python scripts/analyze_bimodality.py --core-only  # Fig 5a/5b/5c (core: cited ≥ 50)
uv run python scripts/plot_fig45_pca_scatter.py --core-only --supervised  # Fig 4 seed axis (paper)
uv run python scripts/plot_fig45_pca_scatter.py  # Fig 4 PCA scatter (appendix, full corpus)
uv run python scripts/analyze_genealogy.py       # Fig 4 genealogy (depends on bimodality output)
uv run python scripts/summarize_core_venues.py   # Core venue tables + institution summaries
uv run python scripts/export_core_venues_markdown.py  # Manuscript-ready top-10 venue markdown table
```

## Citation graph

`citations.csv` (775,288 rows) was built from two sources:

- **Crossref** (`enrich_citations_batch.py`): covers papers where publishers deposit reference lists
- **OpenAlex** (`enrich_citations_openalex.py`): fills the gap using `referenced_works`

**Overall coverage**: 17,248 / 23,194 corpus DOIs (74%) appear as source papers.
**Core coverage** (cited ≥ 50): 2,284 core works.
**Quality**: precision = recall = 1.000 verified against Crossref on 30-paper sample.
**Structural ceiling**: the remaining 22% are at publishers (preprints, small journals, regional outlets) with no API reference metadata. Next step: PDF OCR with GROBID for core papers.

The OpenAlex enrichment uses a two-phase approach:
1. Batch-fetch `referenced_works` (list of OpenAlex IDs) for each corpus DOI via filter endpoint
2. Batch-resolve OpenAlex IDs → DOIs + title/year/journal via `openalex:W1|W2|...` filter

Both scripts are resumable: Crossref uses `.citations_batch_checkpoint.csv`, OpenAlex uses `.citations_oa_done.txt`.

## Intellectual traditions (Table 1)

Empirical detection via co-citation community detection is implemented (`analyze_cocitation.py`, `compare_communities_across_windows.py`). Analysis across four time windows (pre-2007, pre-2015, pre-2020, full) reveals:

- Pre-2007: 18 small, distinct communities — econometrics, institutions, adaptation, aid, CDM, etc.
- Pre-2015: merger into mega-community (97 papers), modularity drops to 0.14
- Post-2020: re-crystallizes into 6 stable communities (Q=0.45): climate risk, governance, adaptation, Paris, green bonds, earth systems

Only the governance/accountability lineage (DiMaggio → Keohane → Weikmans) persists across all four windows.
