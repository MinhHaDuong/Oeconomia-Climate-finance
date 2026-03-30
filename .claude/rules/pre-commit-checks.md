---
paths:
  - "dvc.lock"
  - "dvc.yaml"
  - "scripts/**/*.py"
  - "content/technical-report.qmd"
---

# Pre-commit Checks

Run these checks mentally before every commit.

## DVC lock sanity

If `dvc.lock` is staged, verify the recorded hashes exist in the local cache. If any stage shows "not in cache", the lock file contains phantom hashes — run `dvc repro <stage>` or `dvc commit <stage>` first.

## Stale check

Re-read any project file you modified or relied on. If it contains outdated numbers, stale status, or dead references, fix them in the same commit. The commit is the quality gate — nothing stale gets versioned.

This includes test files: if a refactor moves where a contract is enforced, tests asserting on the old location are dead references — update them in the same commit.

## When to update `content/technical-report.qmd`

- Pipeline phase contract changed (new inputs/outputs)
- New script added or existing script's interface changed
- Data schema changed (columns added/removed in CSV files)
- Methodology changed (embedding model, clustering params, break detection)
- NOT for manuscript prose edits, figure styling, or build tweaks
