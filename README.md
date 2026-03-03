# Climate Finance History - Œconomia Article Project

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

## Repository Structure

```
├── CLAUDE.md                         # AI handoff: data paths, conventions, status
├── PLAN.md                           # Manuscript structure (v3, three-act, five figures)
├── AGENTS.md                         # Writing guidelines, workflow rules, quality standards
├── technical-report.md               # Full pipeline documentation (10 sections)
├── extended abstract.md              # Submitted extended abstract
├── notes.md                          # Working notes, draft arguments
├── scripts/                          # Python analysis pipeline
├── figures/                          # Generated figures (tracked)
├── tables/                           # Generated tables (tracked)
├── data/catalogs/                    # Small curated data (het_core.csv only; rest in ~/data/...)
├── release/                          # Releases outside CIRED. Append-only.
├── attic/                            # Old stuff to delete when paper is accepted
├── AI tech reports/                  # AI-assisted research (SciSpace CSVs + analyses)
├── corpus ISTEX/                     # 484-article dataset (not tracked in git)
├── bibliography/                     # main.bib (PDFs not tracked in git)
└── docs/                             # Œconomia journal info, book project notes
```

## Research Corpus

### Bibliometric corpus (~22,000 works)
Built from multiple sources (OpenAlex, ISTEX, Scopus, JSTOR, BibCNRS, grey literature), merged and deduplicated. Generated data lives at `~/data/projets/Oeconomia-Climate-finance/catalogs/` (see `CLAUDE.md` for details).

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

See `CLAUDE.md` for AI handoff (data paths, conventions, status).
See `PLAN.md` for manuscript structure and drafting plan.

## Contact

- **Managing Editor:** Francesco Sergi (francesco.sergi@u-pec.fr)
- **Journal:** Œconomia – History / Methodology / Philosophy
  - https://journals.openedition.org/oeconomia/
  - http://journals.sfu.ca/oeconomia
