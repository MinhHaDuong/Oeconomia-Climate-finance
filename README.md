# Climate Finance History — Œconomia Article Project

**Title:** Counting Climate Finance: How an Economic Object Was Made (1990–2024)

How economists and institutions co-produced the categories, metrics, and accounting frameworks that made climate finance measurable and governable.

## Documents

| Document | File | Journal | Status |
|----------|------|---------|--------|
| Manuscript | `content/manuscript.qmd` | Œconomia (Varia) | Submitted 2026-03-18, under review |
| Data paper | `content/data-paper.qmd` | RDJ4HSS (diamond OA) | Submitted 2026-03-26, under review |
| Technical report | `content/technical-report.qmd` | HAL working paper | Complete |
| Companion paper | `content/companion-paper.qmd` | Scientometrics / QSS | Outline |

All four are Quarto documents sharing fragments via `content/_includes/`.

## Setup

Prerequisites: [Quarto](https://quarto.org/docs/get-started/) ≥ 1.4, [TinyTeX](https://quarto.org/docs/output-formats/pdf-engine.html) or full TeX Live with XeLaTeX, [uv](https://docs.astral.sh/uv/).

```bash
make setup                              # install git hooks
uv sync                                 # Phase 2/3 deps (figures + manuscript)
uv sync --group corpus --extra cpu      # Phase 1 deps (CPU torch, for doudou)
uv sync --group corpus --extra cu130    # Phase 1 deps (CUDA 13.0, for padme)
uv run dvc cache dir /path/to/dvc-cache # store blobs outside sync/backup dirs
uv run dvc pull                         # download corpus data (~1.3 GB) from padme
```

The DVC cache directory should be outside Nextcloud-synced or snapshotted directories.

On padme (the DVC remote host), also run once:

```bash
uv run dvc remote modify --local padme url /data/projets/dvc/oeconomia-climate-finance
uv run dvc cache dir /data/projets/dvc-cache/oeconomia
```

## Usage

**Padme is the data authority.** The corpus pipeline (Phase 1) runs on padme. Doudou only pulls data — never pushes.

```bash
# On padme — build corpus (auto-pushes data, auto-commits dvc.lock):
make corpus

# On doudou — sync and build:
git pull && uv run dvc pull             # get updated data
make figures                            # regenerate figures and tables (~2 min)
make manuscript                         # build PDF (requires figures)
make papers                             # build all 3 companion documents

# Validation and packaging:
make corpus-validate                    # acceptance tests on corpus
make archive-analysis                   # reproducibility archive (data + scripts)
make archive-manuscript                 # manuscript archive (figures + Quarto)
```

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
├── config/                           # Pipeline parameters (YAML)
├── Makefile                          # Build: make corpus, make figures, make manuscript
├── dvc.yaml                          # Phase 1 pipeline DAG (DVC stages)
├── data/                             # DVC-managed data (dvc pull to populate)
│   ├── catalogs/                    #   Corpus CSVs, embeddings, caches
│   └── pool/                        #   Raw API responses (gzipped JSONL)
├── scripts/                          # Python analysis pipeline
├── docs/                             # Guidelines, journal info, book project notes
├── release/                          # Reproducibility archives & submissions (append-only)
└── attic/                            # Old stuff to delete when paper is accepted
```

## Release

| Submission | Date | Zenodo | HAL | Git tag |
|------------|------|--------|-----|---------|
| Œconomia (Varia) | 2026-03-18 | [10.5281/zenodo.19097045](https://doi.org/10.5281/zenodo.19097045) | [hal-05558422v1](https://hal.science/hal-05558422v1) | `v1.0-submission` |
| RDJ4HSS (data paper) | 2026-03-26 | [10.5281/zenodo.19236130](https://doi.org/10.5281/zenodo.19236130) | — | `v1.1-rdj-submitted` |

Errata 1 (Figure 2 label fix) ready in `release/2026-03-23 Oeconomia errata/`.

## Project documentation

See `STATE.md` for current status, `ROADMAP.md` for milestones, `AGENTS.md` for AI workflow. Pipeline architecture is documented in `.claude/rules/architecture.md`.

## AI agent configuration

The project `.claude/` directory contains only project-specific rules (writing style, architecture, submission workflow). Generic rules, skills, and hooks live in `~/.claude/` as part of the [Imperial Dragon Harness](https://github.com/MinhHaDuong/agentic-harness). See `AGENTS.md` for the full configuration map.

## Contact

minh.ha-duong@cnrs.fr
