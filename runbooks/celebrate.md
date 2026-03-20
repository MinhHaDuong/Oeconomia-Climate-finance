# Celebrate — post-task wrap-up

Run this sequence after completing a task. Do not skip steps.

## `[Doing → Celebrating]`

1. **Reflect**: what worked, what didn't, what was surprising.
2. **Update STATE.md**: refresh stats, remove resolved blockers.
3. **Update ROADMAP.md**: check off completed items, note new ones that emerged.
4. **Update technical-report.qmd** if pipeline, data contract, or methodology changed.
5. **Save persistent memory** (`$CLAUDE_MEMORY_DIR/MEMORY.md` or equivalent): save durable lessons from this task. No sweep here — sweeps happen at session end (`runbooks/celebrate-day.md`).
6. **Commit** the updates on the current branch (before merging).

## Close and clean up

7. **Merge to main**: `git checkout main && git merge --no-ff -m "..." <branch>`.
8. **Push** and **clean up**: delete local and remote branch.
9. **Close** the GitHub issue if one exists.
10. **Check for tracking issue** (integration review): if the closed issue has a parent, check whether all sibling sub-issues are now closed:
    ```bash
    gh issue view <PARENT> --json subIssues
    ```
    - If any sibling is still open: do nothing — tracking issue stays open.
    - If all siblings are now closed, run integration review on the tracking issue:
      1. Re-read all child PR diffs: for each child, find the PR with `gh pr list --search "closes:#<child>"`, then read it with `gh pr diff <PR#>`.
      2. Run tests: `make check`
      3. Check the tracking issue's exit criteria — are they all met?
      4. If gaps remain: open new sub-issues on the tracking issue, leave it open.
      5. If all criteria met: close the tracking issue with a summary comment.
11. **Verify hygiene** — no stale artifacts left behind:
    - `git worktree list` → only main (or active work)
    - `git branch -a` → no stale remote branches from merged PRs
    - `gh issue list` → no orphan issues from completed work
    - `gh pr list` → no stale PRs from merged/superseded branches
12. **Log celebration** — record structured session metrics:
    ```bash
    ~/CNRS/code/agentic-harness/telemetry/bin/log-celebration '{"project":"oeconomia","session_type":"task","commits":N,"prs_merged":N,"deliverables":[...],"surprises":[...],"next":[...]}'
    ```
13. **Offer** to work on AGENTS.md if the workflow can be improved.

## Merge message format

```
Merge <branch>: <one-line summary>

<Tactical detail: architecture decisions, cross-file impacts, residual debt.>
```
