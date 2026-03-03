# CLAUDE.md — AI handoff

See:
- README.md — project overview, theoretical framework, contact
- PLAN.md — manuscript structure (three-act, five figures)
- technical-report.md — full pipeline documentation (10 sections)
- AGENTS.md — writing guidelines, workflow rules, quality standards

## Data

All generated data at `~/data/projets/Oeconomia-Climate-finance/`
(override: `CLIMATE_FINANCE_DATA` env var; see `scripts/utils.py`)

## Conventions

- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- All scripts support `--no-pdf`.

## Status (2026-03-03)

- Corpus: 22,113 refined works, 18,798 with embeddings
- Core subset: 1,176 (cited_by ≥ 50)
- All figures complete (see PLAN.md §1.1)
- **Next: write the manuscript** (PLAN.md Phase 2)
