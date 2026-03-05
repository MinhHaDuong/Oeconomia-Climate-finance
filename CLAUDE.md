# CLAUDE.md — AI handoff

See:
- README.md — project overview, theoretical framework, contact
- PLAN.md — manuscript structure (three-act, five figures)
- AGENTS.md — writing guidelines, workflow rules, quality standards

## Project structure

Quarto multi-document project (`_quarto.yml`). Source files in `content/`, rendered output in `output/`. Four outputs:

| Document | File | Target |
|----------|------|--------|
| Manuscript | `content/manuscript.qmd` | Œconomia (Varia) |
| Technical report | `content/technical-report.qmd` | HAL working paper |
| Data paper | `content/data-paper.qmd` | Scientific Data |
| Companion paper | `content/companion-paper.qmd` | Scientometrics / QSS |

Shared fragments in `content/_includes/` (10 files), reused via `{{< include >}}`.

## Data

All generated data at `~/data/projets/Oeconomia-Climate-finance/`
(override: `CLIMATE_FINANCE_DATA` env var; see `scripts/utils.py`)

## Conventions

- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- All scripts support `--no-pdf`.
- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companion documents. `make figures` regenerates all figures (byte-reproducible).
- House style: `docs/oeconomia-style.md` (eyeballed from 15-4 samples)

## Status (2026-03-05)

- Manuscript: ~9,400 words, 47 bib entries, 2 figures + 1 table
- Corpus: 22,113 refined works, 18,798 with embeddings, 1,176 core
- Quarto refactoring complete: 4 documents, 10 shared includes
- **Next: revision and submission**
