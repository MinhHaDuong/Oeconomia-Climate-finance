# CLAUDE.md — AI handoff

See:
- README.md — project overview, theoretical framework, contact
- PLAN.md — manuscript structure (three-act, five figures)
- technical-report.qmd — full pipeline documentation (10 sections, Quarto + includes)
- AGENTS.md — writing guidelines, workflow rules, quality standards

## Data

All generated data at `~/data/projets/Oeconomia-Climate-finance/`
(override: `CLIMATE_FINANCE_DATA` env var; see `scripts/utils.py`)

## Conventions

- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- All scripts support `--no-pdf`.
- `make` builds all documents (Quarto). `make manuscript` builds manuscript only. `make figures` regenerates all figures (byte-reproducible).
- House style: `docs/oeconomia-style.md` (eyeballed from 15-4 samples)

## Status (2026-03-04)

- Manuscript: ~9,400 words, 47 bib entries, 2 figures + 1 table
- Corpus: 22,113 refined works, 18,798 with embeddings, 1,176 core
- **Next: revision and submission**
