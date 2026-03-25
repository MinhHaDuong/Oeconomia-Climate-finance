# Celebrate — post-task wrap-up

Run this sequence after completing a task. Do not skip steps.

## `[Doing → Celebrating]`

1. **Reflect**: what worked, what didn't, what was surprising.
2. **Update STATE.md**: refresh stats, remove resolved blockers. Do not maintain PR/issue lists — the ticket system is the source of truth.
3. **Update ROADMAP.md**: check off completed items, note new ones that emerged.
4. **Update technical-report.qmd** if pipeline, data contract, or methodology changed.
5. **Save persistent memory** (`$CLAUDE_MEMORY_DIR/MEMORY.md` or equivalent): save durable lessons from this task. No sweep here — sweeps happen at session end (`.agent/runbooks/celebrate-day.md`).
6. **Commit** the updates on the current branch (before merging).

## Close and clean up

7. **Close the ticket** — set `Status: closed` in the header, append a log entry with the reason (`{ISO-timestamp} {agent-id} status closed — {reason}`), and commit on the branch (before merging — the pre-commit hook blocks direct commits on `main`).
8. **Remove the `.wip` signal**:
   ```bash
   rm -f "$(git rev-parse --git-common-dir)/ticket-wip/{ticket-id}.wip"
   ```
9. **Merge to main**: feature work goes through a PR in the ticket system. Chores (dvc.lock, housekeeping) merge locally via short-lived branch + fast-forward.
10. **Push** and **clean up**: delete local and remote branch.
11. **Close** the GitHub issue if one exists.
12. **Check for tracking ticket** (integration review): if the closed ticket has a parent, check whether all sibling sub-tickets are now closed:
    ```bash
    # Local tickets:
    grep -l "^X-Parent: <PARENT_ID>" tickets/*.ticket | xargs grep "^Status:" | grep -v closed
    # Forge tickets:
    gh issue view <PARENT> --json subIssues
    ```
    - If any sibling is still open: do nothing — tracker stays open.
    - If all siblings are now closed, run integration review on the tracking ticket:
      1. Re-read all child PR diffs: for each child, find the PR with `gh pr list --search "closes:#<child>"`, then read it with `gh pr diff <PR#>`.
      2. Run tests: `make check`
      3. Check the tracking ticket's exit criteria — are they all met?
      4. If gaps remain: open new sub-tickets on the tracking ticket, leave it open.
      5. If all criteria met: close the tracking ticket with a summary comment.
13. **Verify hygiene** — no stale artifacts left behind:
    - `git worktree list` → only main (or active work)
    - `git branch -a` → no stale remote branches from merged PRs
    - No orphan tickets from completed work
    - `gh pr list` → no stale PRs from merged/superseded branches
14. **Log celebration** — record structured session metrics (skip if harness not installed):
    ```bash
    ~/.agent/log/log-celebration '{"project":"oeconomia","session_type":"task","commits":N,"prs_merged":N,"deliverables":[...],"surprises":[...],"next":[...]}'
    ```
15. **Offer** to work on AGENTS.md if the workflow can be improved.

## Merge message format

```
Merge <branch>: <one-line summary>

<Tactical detail: architecture decisions, cross-file impacts, residual debt.>
```
