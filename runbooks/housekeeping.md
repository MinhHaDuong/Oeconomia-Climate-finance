# Housekeeping — triggered checks

Run the relevant check at the specified trigger point. Do not skip.

## Before every commit

- **Stale check**: re-read any project file you modified or relied on. If it contains outdated numbers, stale status, or dead references, fix them in the same commit. The commit is the quality gate — nothing stale gets versioned.

## After completing a ticket

See `runbooks/celebrate.md`.

## At conversation start (time-based)

- Read `STATE.md` and `ROADMAP.md` — if not from today, refresh from current data.

## When to update `content/technical-report.qmd`

- Pipeline phase contract changed (new inputs/outputs)
- New script added or existing script's interface changed
- Data schema changed (columns added/removed in CSV files)
- Methodology changed (embedding model, clustering params, break detection)
- NOT for manuscript prose edits, figure styling, or build tweaks
