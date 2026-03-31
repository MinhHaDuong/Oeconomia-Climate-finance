---
paths:
  - "scripts/**/*.py"
  - "tests/**/*.py"
  - "Makefile"
  - "dvc.yaml"
  - "pyproject.toml"
  - "config/**/*"
---

# Coding Rules

## Python (3.10+)

Style:
- Built-in generics: `list[str]`, `dict[str, int]`, `str | None`. Never `from typing import List, Dict, Tuple, Optional`.
- `X | Y` union syntax, not `Union[X, Y]`. No `from __future__ import annotations`.
- No ABC classes. Use Protocol for structural subtyping if needed.
- Type hints where they clarify intent. Skip where they add noise.
- Assertions at system boundaries. Trust internal code.

Script structure:
- **Every entry point gets argparse.** If `__name__ == "__main__"` exists, it gets an `ArgumentParser`.
- **Lean main() functions.** Delegate to well-named helpers.
- **No hardcoded paths.** Use `--output` and `--named-input` CLI params, with defaults from config.
- **No `sys.path` hacks.** Use proper packaging (`pyproject.toml`).
- **Centralize research parameters.** Constants belong in `config/analysis.yaml`, read via `load_analysis_config()`.
- **Logging, not print.** Use `from utils import get_logger; log = get_logger("script_name")`.

Typing policy — core modules (`pipeline_text.py`, `pipeline_io.py`, `pipeline_progress.py`, `enrich_dois.py`) must be fully typed, enforced by mypy in `test_script_hygiene.py::TestTypingCoreModules`. When touching a core module, annotations are required on new/changed functions. Do NOT type: `main()` bodies, plot scripts, DataFrame column access, one-off scripts.

Dependencies: **always `uv sync`** (never pip). `uv run python scripts/...` to execute. Torch extras: `--extra cpu` (doudou) or `--extra cu130` (padme).

## Testing

- Tests live in `tests/test_<module>.py`. A new script or changed behavior starts with a test.
- `make check-fast`: unit tests + prose lint, < 10 s — run during development.
- `make check`: full suite including integration + slow tests — run before opening a PR.
- Acceptance tests (e.g., `make corpus-validate`) are the top-level contract — never weaken without discussion.

| Marker | Meaning | Excluded from |
|--------|---------|---------------|
| *(none)* | Unit test — pure logic, no subprocess, no sleep | — |
| `@pytest.mark.integration` | Spawns subprocesses or uses sleep-based timing | `check-fast` |
| `@pytest.mark.slow` | Requires network access or real corpus data | `check-fast` |

When writing new tests:
- CLI flag presence: check via source inspection (`open().read()` + string match), not subprocess `--help`.
- Tests using `subprocess.run()` or `time.sleep()`: mark `@pytest.mark.integration`.
- Tests needing heavy modules only for `inspect.getsource()`: read the file directly instead.

## Build (Make)

- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companions. `make figures` regenerates all figures (byte-reproducible).
- **One output per rule.** Each target should produce a known file so timestamps work.
- **Sentinel stamps for dynamic outputs.** Use a stamp file when a script produces data-dependent filenames. Add `*.stamp` to `.gitignore`.
- **No `.PHONY` for real work.** Use `.PHONY` only for aliases (`figures`, `stats`, `clean`).
