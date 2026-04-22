---
paths:
  - "scripts/**/*.py"
  - "tests/**/*.py"
  - "Makefile"
  - "dvc.yaml"
  - "pyproject.toml"
  - "config/**/*"
---

# Coding Rules (project-specific)

Generic coding rules are in `~/.claude/rules/coding.md`. This file adds project-specific conventions.

## Python

- **Centralize research parameters.** Constants belong in `config/analysis.yaml`, read via `load_analysis_config()`.
- **Logging**: `from utils import get_logger; log = get_logger("script_name")`.
- Torch extras: `--extra cpu` (doudou) or `--extra cu130` (padme).
- **Always `uv run`**: never bare `python3`, never `.venv/bin/python`. In Makefiles: inline `uv run python`. Deps in `pyproject.toml`.
- **Formatter strips unused imports**: add an import AND its first usage in the same Edit call. If split across calls, Read the file after adding the import to verify it survived the formatter. A PostToolUse warning "formatter modified the file" means check the import immediately.

## Testing

- **Mock os guards**: when mocking `pd.read_csv` on `pipeline_loaders`, also mock `os.path.exists` — `load_refined_works()` checks file existence before reading. Same pattern for any loader that guards with existence checks.
- **Sampling-semantics tests**: for any function named `bootstrap`, `permutation`, `resample`, `subsample`, or `monte_carlo`, schema + row-count assertions are insufficient. Assert the sampling distribution matches the function name (e.g., bootstrap: resample size == input size, duplicates expected across draws).

Typing policy — core modules must be fully typed, enforced by mypy in `test_script_hygiene.py::TestTypingCoreModules` (which owns the canonical module list). When touching a core module, annotations are required on new/changed functions. Do NOT type: `main()` bodies, plot scripts, DataFrame column access, one-off scripts.

## Testing

- Acceptance tests (e.g., `make corpus-validate`) are the top-level contract — never weaken without discussion.

## Build (Make)

- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companions. `make figures` regenerates all figures (byte-reproducible).
- Add `*.stamp` to `.gitignore` for sentinel stamps.
