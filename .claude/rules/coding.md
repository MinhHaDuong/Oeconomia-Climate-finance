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

## Testing

- Tests live in `tests/`. A new script or changed behavior starts with a test in `tests/test_<module>.py`.
- `make check-fast`: unit tests + prose lint, < 10 s — run during development.
- `make check`: full suite including integration + slow tests — run before opening a PR.
- Acceptance tests (e.g., `make corpus-validate`) are the top-level contract — never weaken them without discussion.

### Test markers

| Marker | Meaning | Excluded from |
|--------|---------|---------------|
| *(none)* | Unit test — pure logic, no subprocess, no sleep | — |
| `@pytest.mark.integration` | Spawns subprocesses or uses sleep-based timing | `check-fast` |
| `@pytest.mark.slow` | Requires network access or real corpus data | `check-fast` |

**When writing new tests:**
- CLI flag presence: check via source inspection (`open().read()` + string match), not subprocess `--help`.
- Tests that run a Python script via `subprocess.run()`: mark `@pytest.mark.integration`.
- Tests that use `time.sleep()` or threading timeouts: mark `@pytest.mark.integration`.
- Tests that import heavy modules only for `inspect.getsource()`: read the file directly instead.

## Typing policy

Core library modules (imported by many scripts) must be fully typed. The authoritative list lives in `test_script_hygiene.py::TestTypingCoreModules.TYPED_MODULES` — add new modules there and in `[tool.mypy] files`.

Do NOT type: `main()` bodies, plot scripts, DataFrame column access, or one-off analysis scripts. When touching a core module, annotations are required on new/changed functions.

## Conventions

- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- Plotting scripts accept `--pdf` for optional PDF output. Non-plotting scripts must not accept it (#545).
- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companion documents. `make figures` regenerates all figures (byte-reproducible).
- **Logging, not print** in pipeline scripts. `print()` is OK in CLI tools. Enforced by `test_script_hygiene.py::TestNoBarePrint`.

## Makefile conventions

- **One output per rule.** Each Make target should produce a known file so timestamps work.
- **Sentinel stamps for dynamic outputs.** Use a stamp file when a script produces data-dependent filenames. Add `*.stamp` to `.gitignore`.
- **No `.PHONY` for real work.** Use `.PHONY` only for aliases (`figures`, `stats`, `clean`).

## Script hygiene

- **No `sys.path` hacks.** Use proper packaging (`pyproject.toml`).
- **Centralize research parameters.** Constants belong in `config/analysis.yaml`, read via `load_analysis_config()`.
- **Every entry point gets argparse.** If `__name__ == "__main__"` exists, it gets an `ArgumentParser`.
- **Loops on API calls check return status and have a circuit breaker.** Abort after N consecutive failures rather than retrying indefinitely (#590).

## Python style (3.10+)

- Modern typing idioms (built-in generics, `X | Y` unions, no `__future__` annotations). Enforced by ruff UP rules in `test_script_hygiene.py::TestRuffModernPython`.
- No ABC classes. Use Protocol for structural subtyping if needed.
- Type hints where they clarify intent. Skip where they add noise.
- Assertions at system boundaries. Trust internal code.

## Dependency management

- **Always use `uv sync`** to install. Never `pip` or `uv pip`.
- torch extras: `--extra cpu` (doudou) or `--extra cu130` (padme, CUDA 13.0).

