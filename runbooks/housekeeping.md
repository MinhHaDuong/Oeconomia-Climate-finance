# Housekeeping — triggered checks

Run the relevant check at the specified trigger point. Do not skip.

## Before every commit

- **Stale check**: re-read any project file you modified or relied on. If it contains outdated numbers, stale status, or dead references, fix them in the same commit. The commit is the quality gate — nothing stale gets versioned. This includes test files: if a refactor moves where a contract is enforced (e.g., from a Makefile recipe to a DVC stage, from a script to a config), tests asserting on the old location are dead references — update them in the same commit, not as a separate ticket.

## After completing a ticket

See `runbooks/celebrate.md`.

## At conversation start (time-based)

- Read `STATE.md` and `ROADMAP.md` — if not from today, refresh from current data.

## Monthly: stale memory sweep

Trigger: first conversation of each month (check `MEMORY.md` header date or last git touch).

1. Scan every entry in `$CLAUDE_MEMORY_DIR/MEMORY.md` against the staleness criteria in `runbooks/memory.md`.
2. Scan every `project_*.md` file: if the project state it describes is complete or superseded, delete the file and remove its MEMORY.md pointer.
3. Check list-type sections against their caps; evict excess entries.
4. Confirm or reset the clock on any TTL-bearing entry that has expired.
5. Commit the sweep on `main` with message `housekeeping: monthly memory sweep YYYY-MM`.

## When to update `content/technical-report.qmd`

- Pipeline phase contract changed (new inputs/outputs)
- New script added or existing script's interface changed
- Data schema changed (columns added/removed in CSV files)
- Methodology changed (embedding model, clustering params, break detection)
- NOT for manuscript prose edits, figure styling, or build tweaks
