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
- `make check-fast`: unit tests + prose lint, < 20 s — run during development.
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

Core library modules (imported by many scripts) must be fully typed:
- `pipeline_text.py`, `pipeline_io.py`, `pipeline_progress.py`, `enrich_dois.py`
- Enforced by mypy in `test_script_hygiene.py::TestTypingCoreModules`
- Add new modules to the `TYPED_MODULES` list and `[tool.mypy] files` when they become shared infrastructure

Do NOT type:
- `main()` function bodies (argparse + orchestration, return None — add `-> None` but skip param annotations)
- Plot scripts (matplotlib is inherently untyped)
- DataFrame column access (pandas has no column-level types)
- One-off analysis scripts

When touching a core module, annotations are required on new/changed functions.

## Conventions

- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- All scripts support `--no-pdf`.
- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companion documents. `make figures` regenerates all figures (byte-reproducible).
- **Logging, not print — in pipeline scripts.** Scripts that transform data or produce figures use `from utils import get_logger` — never bare `print()`. CLI tools that report to the user (not part of the pipeline) may use `print()` for stdout. The test enforces this by prefix; see `test_script_hygiene.py::TestNoBarePrint` for the exact scope.

## Makefile conventions

- **One output per rule.** Each Make target should produce a known file so timestamps work.
- **Sentinel stamps for dynamic outputs.** Use a stamp file when a script produces data-dependent filenames. Add `*.stamp` to `.gitignore`.
- **No `.PHONY` for real work.** Use `.PHONY` only for aliases (`figures`, `stats`, `clean`).

## Script hygiene

- **No `sys.path` hacks.** Use proper packaging (`pyproject.toml`).
- **Centralize research parameters.** Constants belong in `config/analysis.yaml`, read via `load_analysis_config()`.
- **Every entry point gets argparse.** If `__name__ == "__main__"` exists, it gets an `ArgumentParser`.

## Python style (3.10+)

- Built-in generics: `list[str]`, `dict[str, int]`, `str | None`. Never `from typing import List, Dict, Tuple, Optional`.
- `X | Y` union syntax, not `Union[X, Y]`.
- No `from __future__ import annotations`.
- No ABC classes. Use Protocol for structural subtyping if needed.
- Type hints where they clarify intent. Skip where they add noise.
- Assertions at system boundaries. Trust internal code.

## Dependency management

- **Always use `uv sync`** to install. Never `pip` or `uv pip`.
- torch extras: `--extra cpu` (doudou) or `--extra cu130` (padme, CUDA 13.0).

## Data location

- Data lives **outside the repo**, at `CLIMATE_FINANCE_DATA` in `.env`.
- `scripts/utils.py` reads `.env` and exports `DATA_DIR`, `CATALOGS_DIR`, `EMBEDDINGS_PATH`. Never hardcode `data/catalogs/` relative to the repo.

## Project structure

Quarto multi-document project (`_quarto.yml`). Four outputs share reusable fragments in `content/_includes/`:

- `content/manuscript.qmd` — main article (self-contained)
- `technical-report.qmd` — pipeline documentation (composed of includes)
- `data-paper.qmd` — corpus data paper
- `companion-paper.qmd` — methods companion

## Pipeline phases

**Phase 1 — Corpus building** (slow, API-dependent, run rarely).
- Scripts: `catalog_*`, `enrich_*`, `qa_*`, `qc_*`, `corpus_*`
- Four steps with intermediate artifacts:
  1. **corpus-discover**: merge sources → `unified_works.csv`
  2. **corpus-enrich**: enrich DOIs/abstracts/citations → `enriched_works.csv`
  3. **corpus-extend**: flag all works (no rows removed) → `extended_works.csv`
  4. **corpus-filter**: apply policy, audit → `refined_works.csv`
- Phase 1 → Phase 2 **contract**: `refined_works.csv`, `embeddings.npz`, `citations.csv`

**Phase 2 — Analysis & figures** (fast, deterministic, run often):
- Scripts: `analyze_*`, `plot_*`, `compute_*`, `export_*`, `summarize_*`, `build_het_core.py`
- Reads Phase 1 outputs; produces `content/figures/`, `content/tables/`, `content/_includes/`, `content/*-vars.yml`

**Phase 3 — Render** (Quarto → PDF/DOCX):
- Reads Phase 2 outputs. Build artifacts go to `output/` (gitignored).

**Phase 4 — Release & archives** (reproducibility packaging):
- Scripts: `release/scripts/build_*_archive.sh`
- Templates: `release/templates/` (Makefiles, READMEs, Dockerfiles shipped in archives)
- Reads Phase 2/3 outputs; produces `*.tar.gz` reproducibility archives

## Incremental caches vs DVC outputs

- **`enrich_cache/`** — persistent cache directory (gitignored, not a DVC output). Survives `dvc repro`.
- **DVC output** — declared in `dvc.yaml` `outs:`. Ephemeral — DVC may delete it.

When adding a new enrichment script: put incremental state in `enrich_cache/<name>.csv`, write the DVC output separately.
