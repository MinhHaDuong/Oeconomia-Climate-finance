# Celebrate the day — session wrap-up

Run when the user ends a work session ("done for today", "let's stop", "wrap up").

## Steps

1. **Reflect on the session** — summarize what got done across all tasks/conversations today.
   `git log --since="6am" --oneline` as a starting point.
2. **Push all branches** — no local-only work overnight.
   `git branch` → for each non-main branch, ensure it's pushed.
3. **Commit WIP if needed** — if there's uncommitted work on a branch, commit with `wip:` prefix and push.
4. **Handoff notes** — for any in-progress ticket with unpushed context, add a GitHub comment: what's done, what's next, blockers.
5. **Hygiene sweep**:
   - `git worktree list` → only main or active work
   - `git branch -a` → no stale remote branches
   - `gh issue list` → no orphan issues
   - `gh pr list` → no stale PRs
6. **Refresh STATE.md** — update date, stats, active work section. Commit on main.
7. **Memory sweep** — follow `runbooks/memory.md` (includes runbook cross-reference).
