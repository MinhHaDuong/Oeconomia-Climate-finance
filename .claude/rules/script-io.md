# Script I/O Discipline

When creating or modifying scripts in `scripts/`:

## Required: --output argument

Every script that produces a file must accept `--output <path>` (required, no default).
The Makefile passes the target path via `$@`.

```python
parser.add_argument("--output", type=str, required=True,
                    help="Output file path")
```

## Optional: --input argument

Scripts that read from the Phase 1→2 contract files (refined_works.csv, etc.)
may use `CATALOGS_DIR` as default. Scripts that read from other sources should
accept `--input` to make dependencies explicit.

## Save path

Use `os.path.splitext(args.output)[0]` as the stem passed to `save_figure()`,
which appends the extension. This way the Makefile controls the output path.

## Makefile convention

```makefile
content/figures/fig_NAME.png: scripts/plot_fig_NAME.py scripts/utils.py $(REFINED)
    uv run python $< --output $@ --no-pdf
```

## Migration

Scripts are migrated one-by-one as touched. Not all scripts are migrated yet.
When editing a script, check if it follows this pattern. If not, migrate it
in the same commit if the change is small, or open a follow-up ticket.
