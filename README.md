8# Climate Finance History - Œconomia Article Project

**Title:** Counting Climate Finance: How an Economic Object Was Made (1990-2025)

## Project Overview

This project analyzes the history of climate finance as an economic object, examining how economists and institutions (OECD DAC, UNFCCC, multilateral development banks) co-produced the categories, metrics, and accounting frameworks that made climate finance measurable and governable between 1990-2025.

## Rationale

Publishing a few articles to lay the groundwork for a book project described in `docs/projet livre...`

## Current State

2026-01-14 Submitted to OEconomia special issue "History of Climate Economics". See `release/2026-01-14...`
2026-02-16 Not selected. However, editor Francesco Sergi encouraged resubmission as regular "Varia" contribution, citing quality and journal fit. See `20260216 decision.txt`.
2026-02-18 Manuscript plan established. See `PLAN.md`.
2026-02-26 Bibliometric analysis complete. Three-act periodization from breakpoint detection.
2026-03-03 All figures finalized (core subset, censored breaks, PCA scatter). Ready for manuscript drafting.
2026-03-05 Refactored into Quarto multi-document project (4 outputs, shared includes).

## Documents

| Document | File | Target journal | Status |
|----------|------|----------------|--------|
| Manuscript | `content/manuscript.qmd` | Œconomia (Varia) | Draft, revising |
| Technical report | `content/technical-report.qmd` | HAL working paper | Complete |
| Data paper | `content/data-paper.qmd` | Scientific Data | Outline + reused sections |
| Companion paper | `content/companion-paper.qmd` | Scientometrics / QSS | Outline |

All four are Quarto documents sharing fragments via `{{< include >}}` from `content/_includes/`.

## Prerequisites

- **[Quarto](https://quarto.org/docs/get-started/)** (≥ 1.4) — document rendering (`make manuscript`, `make papers`)
- **[TinyTeX](https://quarto.org/docs/output-formats/pdf-engine.html)** or a full TeX Live install with XeLaTeX — PDF output (`quarto install tinytex` after installing Quarto)
- **[uv](https://docs.astral.sh/uv/)** — Python dependency management (figures, corpus pipeline)

## Repository Structure

```
├── _quarto.yml                       # Quarto project config (4 documents)
├── content/                          # All Quarto source material
│   ├── manuscript.qmd                # Main article (Œconomia)
│   ├── technical-report.qmd          # Full pipeline documentation (10 sections)
│   ├── data-paper.qmd                # Corpus data paper (Scientific Data)
│   ├── companion-paper.qmd           # Methods companion (Scientometrics/QSS)
│   ├── _includes/                    # Shared Markdown fragments (10 files)
│   ├── bibliography/                 # main.bib + oeconomia.csl
│   ├── figures/                      # Generated figures (tracked, see below)
│   └── tables/                       # Generated tables (tracked, see below)
├── output/                           # Quarto rendered output (gitignored)
├── CLAUDE.md                         # AI handoff: lean index + status
├── PLAN.md                           # Manuscript structure (three-act, five figures)
├── AGENTS.md                         # Writing guidelines, workflow rules, quality standards
├── Makefile                          # Build: make manuscript, make papers, make figures
├── scripts/                          # Python analysis pipeline
├── release/                          # Releases outside CIRED. Append-only.
├── docs/                             # Œconomia journal info, book project notes
└── attic/                            # Old stuff to delete when paper is accepted
```

## Data

All generated data at `~/data/projets/Oeconomia-Climate-finance/`
(override: `CLIMATE_FINANCE_DATA` env var; see `scripts/utils.py`).

`content/figures/` and `content/tables/` (including interactive HTML) are tracked in git.
They are regenerable via `make figures`, but tracking them ensures the
documents build from a fresh clone without running the full data pipeline.

## Literature Indexing Pipeline

Multi-source catalog of academic and grey literature on climate finance.
All sources searched for: `"climate finance" OR "finance climat" OR "finance climatique"`.

### Data inventory

| File | Rows | Description |
|------|------|-------------|
| `catalogs/istex_works.csv` | 482 | ISTEX corpus (local JSON metadata) |
| `catalogs/istex_refs.csv` | 19,744 | Cited references extracted from ISTEX articles |
| `catalogs/openalex_works.csv` | 11,313 | OpenAlex API query (free, no auth) |
| `catalogs/bibcnrs_works.csv` | 242 | bibCNRS exports: French, Chinese, Japanese, German (deduplicated) |
| `catalogs/scispsace_works.csv` | 663 | SciSpace AI-curated corpus (RIS + CSV, deduplicated) |
| `catalogs/grey_works.csv` | 213 | 16 curated seed entries + 200 World Bank OKR API |
| `catalogs/unified_works.csv` | 12,372 | Deduplicated merge of all sources (474 multi-source) |
| `catalogs/citations.csv` | 232,218 | Crossref citation links (176K with DOIs, from 4,710 source DOIs) |

### CSV schema

**Works** (`*_works.csv`):
`source, source_id, doi, title, first_author, all_authors, year, journal, abstract, language, keywords, categories, cited_by_count, affiliations`

**References** (`istex_refs.csv`, `citations.csv`):
`source_doi, source_id, ref_doi, ref_title, ref_first_author, ref_year, ref_journal, ref_raw`

### Scripts

| Script | Source | Auth required |
|--------|--------|---------------|
| `catalog_istex.py` | Local JSON files | No |
| `catalog_openalex.py` | OpenAlex API | No (free, polite pool) |
| `catalog_grey.py` | YAML seed + World Bank OKR API | No |
| `catalog_bibcnrs.py` | bibCNRS RIS exports | Yes (CNRS Janus) |
| `catalog_scispsace.py` | SciSpace AI tech reports | No (local files) |
| `catalog_merge.py` | Merges all `*_works.csv` | No |
| `enrich_citations.py` | Crossref API | No (polite pool) |

Retired: `catalog_scopus.py` and `catalog_jstor.py` — OpenAlex already indexes their content.

### How to re-run

1. **Re-merge after changes**: `python3 scripts/catalog_merge.py`
2. **Refresh OpenAlex**: `python3 scripts/catalog_openalex.py`
3. **Update grey literature**: edit `config/grey_sources.yaml`, run `python3 scripts/catalog_grey.py`
4. **Add bibCNRS exports**: save RIS files to exports dir, run `python3 scripts/catalog_bibcnrs.py`, then re-merge

### Known limitations

- Crossref enrichment resolved 4,710/10,347 DOIs (rest returned 404)
- Grey literature coverage is partial: OECD iLibrary and UNFCCC have no bulk API
- OpenAlex under-represents non-English literature; bibCNRS adds 233 non-English works
- Chinese-language literature (CNKI) remains largely uncovered

## Key Themes

1. **Categorization:** How OECD DAC categories (grants/loans, bilateral/multilateral, Rio markers) structured climate finance
2. **Quantification:** Grant-equivalent methodology, face value debates, mobilized private finance accounting
3. **Controversies:** OECD vs. Oxfam methodologies, additionality, double counting
4. **Actors:** Economists as policy experts (Jan Corfee-Morlot, Nicholas Stern, HLPF 2010)
5. **Governance:** $100bn commitment → $300bn NCQG transition (Copenhagen to Baku)

## Theoretical Framework

- **Sociology of quantification:** Desrosières (commensuration), Porter (trust in numbers)
- **Performativity:** Callon, MacKenzie (how metrics shape reality)
- **Economization:** Fourcade, Çalışkan
- **History of economic thought:** Development economics + environmental economics genealogy
- **STS:** Boundary work, infrastructures of knowledge

## Next Steps

See `CLAUDE.md` for AI handoff (lean index + status).
See `PLAN.md` for manuscript structure and drafting plan.
See `AGENTS.md` for writing guidelines, conventions, and workflow rules.

## Contact

- **Managing Editor**
- **Journal:** Œconomia – History / Methodology / Philosophy
  - https://journals.openedition.org/oeconomia/
  - http://journals.sfu.ca/oeconomia
