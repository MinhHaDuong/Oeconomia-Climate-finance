# Climate Finance History — Œconomia Article Project

**Title:** Counting Climate Finance: How an Economic Object Was Made (1990–2025)

## Vision

This project analyzes the history of climate finance as an economic object, examining how economists and institutions (OECD DAC, UNFCCC, multilateral development banks) co-produced the categories, metrics, and accounting frameworks that made climate finance measurable and governable between 1990–2025.

It is intellectual history that uses climate finance as a case study for understanding how economists create governable objects through quantification.

## Rationale

Publishing a few articles to lay the groundwork for a book project described in `docs/projet livre - pitch.md`

## Documents

| Document | File | Target journal | Status |
|----------|------|----------------|--------|
| Manuscript | `content/manuscript.qmd` | Œconomia (Varia) | Draft, revising |
| Technical report | `content/technical-report.qmd` | HAL working paper | Complete |
| Data paper | `content/data-paper.qmd` | Scientific Data | Outline + reused sections |
| Companion paper | `content/companion-paper.qmd` | Scientometrics / QSS | Outline |

All four are Quarto documents sharing fragments via `{{< include >}}` from `content/_includes/`.

## Key themes

1. **Categorization:** How OECD DAC categories (grants/loans, bilateral/multilateral, Rio markers) structured climate finance
2. **Quantification:** Grant-equivalent methodology, face value debates, mobilized private finance accounting
3. **Controversies:** OECD vs. Oxfam methodologies, additionality, double counting
4. **Actors:** Economists as policy experts (Jan Corfee-Morlot, Nicholas Stern, HLPF 2010)
5. **Governance:** $100bn commitment → $300bn NCQG transition (Copenhagen to Baku)

## Theoretical framework

- **Sociology of quantification:** Desrosières (commensuration), Porter (trust in numbers)
- **Performativity:** Callon, MacKenzie (how metrics shape reality)
- **Economization:** Fourcade, Çalışkan
- **History of economic thought:** Development economics + environmental economics genealogy
- **STS:** Boundary work, infrastructures of knowledge

## Prerequisites

- **[Quarto](https://quarto.org/docs/get-started/)** (≥ 1.4) — document rendering
- **[TinyTeX](https://quarto.org/docs/output-formats/pdf-engine.html)** or full TeX Live with XeLaTeX — PDF output
- **[uv](https://docs.astral.sh/uv/)** — Python dependency management

## Repository structure

```
├── _quarto.yml                       # Quarto project config (4 documents)
├── content/                          # All Quarto source material
│   ├── manuscript.qmd                # Main article (Œconomia)
│   ├── technical-report.qmd          # Full pipeline documentation
│   ├── data-paper.qmd                # Corpus data paper
│   ├── companion-paper.qmd           # Methods companion
│   ├── _includes/                    # Shared Markdown fragments
│   ├── bibliography/                 # main.bib + oeconomia.csl
│   ├── figures/                      # Generated figures (gitignored)
│   └── tables/                       # Generated tables (gitignored)
├── output/                           # Quarto rendered output (gitignored)
├── CLAUDE.md                         # AI redirect → AGENTS.md
├── AGENTS.md                         # AI workflow orchestration
├── ROADMAP.md                        # Milestones and deliverables
├── STATE.md                          # Current decisions and blockers
├── Makefile                          # Build: make manuscript, make papers, make figures
├── scripts/                          # Python analysis pipeline
├── docs/                             # Guidelines, journal info, book project notes
├── release/                          # Releases outside CIRED. Append-only.
└── attic/                            # Old stuff to delete when paper is accepted
```

## Data

All generated data at `~/data/projets/Oeconomia-Climate-finance/`
(override: `CLIMATE_FINANCE_DATA` env var in `.env`; see `scripts/utils.py`).

`content/figures/` and `content/tables/` are gitignored — they are 100% script-generated.
After cloning, regenerate them before building documents:

```bash
make corpus-validate  # run 44-check acceptance test
make corpus-tables    # regenerate per-source stats, citation coverage, QC report
make figures          # regenerate all figures and tables (~2 min)
make manuscript       # build PDF (requires figures)
```

## Project documentation

| File | Purpose |
|------|---------|
| `AGENTS.md` | AI workflow orchestration, Dragon Dreaming phases, git discipline |
| `ROADMAP.md` | Milestones: what's done, what's next |
| `STATE.md` | Current snapshot: stats, blockers, priorities |
| `docs/writing-guidelines.md` | Manuscript prose style, language polish rules |
| `docs/coding-guidelines.md` | Pipeline phases, script reference, conventions |
| `docs/oeconomia-style.md` | Journal house style |

## Contact

- **Journal:** Œconomia – History / Methodology / Philosophy
  - https://journals.openedition.org/oeconomia/
  - http://journals.sfu.ca/oeconomia
