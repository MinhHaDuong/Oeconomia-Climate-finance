# Celebrate — post-task wrap-up

Run this sequence after completing a task. Do not skip steps.

## Steps

1. **Reflect**: what worked, what didn't, what was surprising.
2. **Update STATE.md**: refresh stats, remove resolved blockers, adjust priorities.
3. **Update ROADMAP.md**: check off completed items, note new ones that emerged.
4. **Update technical-report.qmd** if pipeline, data contract, or methodology changed.
5. **Update persistent memory** (`$CLAUDE_MEMORY_DIR/MEMORY.md` or equivalent): save durable lessons, prune stale entries.
6. **Commit** the updates on the current branch (before merging).
7. **Merge to main**: `git checkout main && git merge --no-ff -m "..." <branch>`.
8. **Push** and **clean up**: delete local and remote branch.
9. **Close** the GitHub issue if one exists.
10. **Verify hygiene** — no stale artifacts left behind:
    - `git worktree list` → only main (or active work)
    - `gh issue list` → no orphan issues from completed work
    - `gh pr list` → no stale PRs from merged/superseded branches
11. **Offer** to work on AGENTS.md if the workflow can be improved.

## Merge message format

```
Merge <branch>: <one-line summary>

<Tactical detail: architecture decisions, cross-file impacts, residual debt.>
```
