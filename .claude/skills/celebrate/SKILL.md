---
name: celebrate
description: Post-task wrap-up. Reflects on completed work, updates project state, cleans up branches.
disable-model-invocation: false
user-invocable: true
---

# Celebrate — post-task wrap-up

`[Doing → Celebrating]`

Do not skip steps.

## Reflect and update

1. **Reflect**: what worked, what didn't, what was surprising.
2. **Sweep for similar patterns**: review the fix just completed. Grep/audit the codebase for the same anti-pattern in other files. File tickets for all instances found.
3. **Update STATE.md**: refresh stats, remove resolved blockers.
4. **Update ROADMAP.md**: check off completed items, note new ones.
5. **Update technical-report.qmd** if pipeline, data contract, or methodology changed.
6. **Save persistent memory**: durable lessons from this task. No sweep here — sweeps happen at `/end-session`.
7. **Commit** the updates on the current branch (before merging).

## Close and clean up

8. **Merge to main**: feature work through PR. Chores merge locally via short-lived branch + fast-forward.
9. **Push** and **clean up**: delete local and remote branch.
10. **Close** the ticket if still open.
11. **Check for tracking ticket**: if the closed ticket has a parent, check whether all sibling sub-tickets are now closed.
    - All closed → integration review: re-read all child PR diffs, run `make check`, verify exit criteria.
    - Any open → do nothing, tracker stays open.
12. **Verify hygiene**:
    - `git worktree list` → only main (or active work)
    - `git branch -a` → no stale remote branches
    - `gh pr list` → no stale PRs
13. **Log celebration** (skip if harness not installed):
    ```bash
    ~/.agent/log/log-celebration '{"project":"oeconomia","session_type":"task",...}'
    ```
14. **Offer** to work on AGENTS.md if the workflow can be improved.
