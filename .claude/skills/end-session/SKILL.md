---
name: end-session
description: End-of-day session wrap-up. Pushes branches, runs tests, refreshes STATE, offers autonomous session.
disable-model-invocation: false
user-invocable: true
---

# End session — day wrap-up

Run when the user ends a work session ("done for today", "let's stop", "wrap up").

## Steps

1. **Reflect on the session** — summarize work done. `git log --since="6am" --oneline` as starting point.
2. **Push all branches** — no local-only work overnight. `git branch` → ensure each non-main branch is pushed.
3. **Commit WIP if needed** — uncommitted work gets `wip:` prefix and push.
4. **Handoff notes** — for in-progress tickets with unpushed context, add a GitHub comment: what's done, what's next, blockers.
5. **Hygiene sweep**:
   - `git worktree list` + scan for stale worktree directories
   - `git branch -a` → delete stale remote branches
   - `gh issue list` → no orphan issues
   - `gh pr list` → no stale PRs
6. **Full test suite** — `make check` on main. New failures → open ticket (tag `bug`). Known failures → confirm still open.
7. **Refresh STATE.md** on a throwaway branch:
   a. `git checkout -b housekeeping-state-YYYY-MM-DD main`
   b. Update date, stats, blockers, next actions.
   c. Commit, merge to main via fast-forward, delete branch.
8. **Memory sweep** — follow `/memory` skill (includes staleness check + rule cross-reference).
9. **Log celebration** (skip if harness not installed).
10. **Autonomous session** — offer to launch `/autonomous` if user wants unsupervised exploration.
