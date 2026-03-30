# Script I/O Discipline

When creating or modifying scripts in `scripts/`:

## Use the shared I/O parser

Import `parse_io_args` and `validate_io` from `script_io_args.py`:

```python
from script_io_args import parse_io_args, validate_io

def main():
    io_args, extra = parse_io_args()       # --output (required), --input (optional)
    validate_io(output=io_args.output)      # fail fast if output dir missing

    # Script-specific args parsed from 'extra'
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(extra)

    # ... computation ...

    out_path = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_path, pdf=args.pdf, dpi=DPI)
```

## Required: --output argument

Every script that produces a file must accept `--output <path>` (required, no default).
The Makefile passes the target path via `$@`.

## Optional: --input argument

Scripts that read from the Phase 1→2 contract files (refined_works.csv, etc.)
may use `CATALOGS_DIR` as default. Scripts that read from other sources should
accept `--input` to make dependencies explicit.

## Save path

Use `os.path.splitext(io_args.output)[0]` as the stem passed to `save_figure()`,
which appends the extension. This way the Makefile controls the output path.

## Makefile convention

```makefile
content/figures/fig_NAME.png: scripts/plot_fig_NAME.py scripts/utils.py $(REFINED)
    uv run python $< --output $@
```

## Migration

Scripts are migrated one-by-one as touched. Not all scripts are migrated yet.
When editing a script, check if it follows this pattern. If not, migrate it
in the same commit if the change is small, or open a follow-up ticket.
