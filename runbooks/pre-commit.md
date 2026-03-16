# Pre-commit — before every commit trigger

Run before every commit.

## Stale check

Re-read any project file you modified or relied on. If it contains outdated numbers, stale status, or dead references, fix them in the same commit. The commit is the quality gate — nothing stale gets versioned.

This includes test files: if a refactor moves where a contract is enforced (e.g., from a Makefile recipe to a DVC stage, from a script to a config), tests asserting on the old location are dead references — update them in the same commit, not as a separate ticket.

## When to update `content/technical-report.qmd`

- Pipeline phase contract changed (new inputs/outputs)
- New script added or existing script's interface changed
- Data schema changed (columns added/removed in CSV files)
- Methodology changed (embedding model, clustering params, break detection)
- NOT for manuscript prose edits, figure styling, or build tweaks
