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
├── data/catalogs/                    # Small curated data (het_core.csv only; rest in ~/data/...)
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

## Research Corpus

### Bibliometric corpus (~22,000 works)
Built from multiple sources (OpenAlex, ISTEX, Scopus, JSTOR, BibCNRS, grey literature), merged and deduplicated. Generated data lives at `~/data/projets/Oeconomia-Climate-finance/catalogs/`.

### Primary Literature
- **ISTEX corpus:** 484 articles with "Climate finance" OR "Finance climat" OR "Finance climatique" (full-text PDFs)
- Located in: `corpus ISTEX/istex-subset-2025-11-27/`

### Systematic Reviews (SciSpace)
Topic-specific analyses with CSV datasets:
- Additionality debates
- Double counting and transparency
- OECD Rio markers methodology
- Grant-equivalent vs. concessionality
- Mobilized private finance
- Performativity and STS perspectives
- UNFCCC Standing Committee on Finance
- Historical evolution (1990-2025)

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
