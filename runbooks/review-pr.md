# Review PR — fresh-context code review

Run this in a fresh context (no shared history with the implementing agent).

## Steps

1. **Read the issue** linked to the PR. Note the exit criteria.
2. **Read the diff**: `gh pr diff <number>`
3. **Check exit criteria**: does the diff satisfy every item?
4. **Run tests**: `make check` (lint-prose + pytest)
5. **Run build**: `make manuscript` (if prose changed)
6. **Check for stale info**: are STATE.md, ROADMAP.md, docs/* consistent with the changes?
7. **Post review**: `gh pr review <number> --comment --body "..."` or `--approve` / `--request-changes`

## What to look for

- Does every changed file have a reason in the commit message?
- Are there new files that should be in .gitignore?
- Do commit messages explain *why*, not just *what*?
- Any secrets, large files, or conflict markers? (hook should catch, but verify)
- Any blacklisted AI-tell words introduced? (`make lint-prose`)
