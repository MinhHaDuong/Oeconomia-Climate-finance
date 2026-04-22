# Session Start (project-specific)

Generic session workflow is in `~/.claude/rules/workflow.md`. This file adds project-specific details.

## Worktree file copying

`.worktreeinclude` auto-copies `.env` and `.dvc/config.local` into the worktree.

## When to Ask the Author

In addition to the generic escalation protocol:
- See writing rules for manuscript-specific guidance.

## Harness behaviour

- **Rules files are linter-protected in the main checkout**: `.claude/rules/` files are loaded into context at session start; the harness keeps disk and context in sync by restoring them. Always edit rule files from a worktree (EnterWorktree), not the main checkout.
