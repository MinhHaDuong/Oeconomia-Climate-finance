---
globs: ["scripts/**"]
---

# Script I/O Discipline

When creating or modifying scripts in `scripts/`:

## Use the shared I/O parser

Import `parse_io_args` and `validate_io` from `script_io_args.py`. For a working example, read `plot_fig1_bars.py`. Tested in `test_io_discipline.py::TestParseIoArgs`.

## Required: --output argument

Every script that produces a file must accept `--output <path>` (required, no default). The Makefile passes the target path via `$@`.

## Optional: --input argument

Scripts that read from the Phase 1→2 contract files may use `CATALOGS_DIR` as default. Scripts that read from other sources should accept `--input` to make dependencies explicit.

## Save path

Use `os.path.splitext(io_args.output)[0]` as the stem passed to `save_figure()`, which appends the extension. This way the Makefile controls the output path.

## Migration

Scripts are migrated one-by-one as touched. Not all scripts are migrated yet. When editing a script, check if it follows this pattern. If not, migrate it in the same commit if the change is small, or open a follow-up ticket.
