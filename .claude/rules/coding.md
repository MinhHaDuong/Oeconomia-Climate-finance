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

Typing policy — core modules must be fully typed, enforced by mypy in `test_script_hygiene.py::TestTypingCoreModules` (which owns the canonical module list). When touching a core module, annotations are required on new/changed functions. Do NOT type: `main()` bodies, plot scripts, DataFrame column access, one-off scripts.

## Testing

- Acceptance tests (e.g., `make corpus-validate`) are the top-level contract — never weaken without discussion.

## Build (Make)

- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companions. `make figures` regenerates all figures (byte-reproducible).
- Add `*.stamp` to `.gitignore` for sentinel stamps.
