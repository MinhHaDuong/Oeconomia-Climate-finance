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

## Status (2026-03-04)

- Corpus: 22,113 refined works, 18,798 with embeddings
- Core subset: 1,176 (cited_by ≥ 50)
- All figures complete (see PLAN.md §1.1)
- YAML front matter + Pandoc figure declarations added to manuscript (T5 — PR #15)
- Introduction drafted with historiographical positioning (A2) and corpus caveat (A1) — PR #15
- **Next:** body sections I–IV (PLAN.md Phase 2); bibliography audit (PLAN.md §1.2)
