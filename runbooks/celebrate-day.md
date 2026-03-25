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
   - `git worktree list` + scan parent dirs and `/tmp` for stale worktree directories
   - `git branch -a` → delete stale remote branches
   - `gh issue list` → no orphan issues
   - `gh pr list` → no stale PRs
6. **Full test suite** — run `make check` on main. For each new failure:
   open a ticket with the error output (tag `bug`). Known failures already
   ticketed just get confirmed still open. Note test status in STATE blockers.
7. **Refresh STATE.md** on a throwaway branch:
   a. `git checkout -b housekeeping-state-YYYY-MM-DD main`
   b. `gh pr list --state open` → update "Active PRs" section.
   c. `git log --oneline -5` → update "Recent" section.
   d. Update date, stats, blockers (including test failures from step 6), next actions.
   e. Commit: `housekeeping: refresh STATE YYYY-MM-DD`
   f. `git checkout main && git merge --no-ff -m "..." housekeeping-state-YYYY-MM-DD`
   g. `git branch -d housekeeping-state-YYYY-MM-DD`
   h. Return to the conversation's working branch.
8. **Memory sweep** — follow `runbooks/memory.md` (includes runbook cross-reference).
9. **Log celebration** — record structured session metrics:
    ```bash
    ~/CNRS/code/agentic-harness/telemetry/bin/log-celebration '{"project":"oeconomia","session_type":"day","commits":N,"prs_merged":N,"memories_saved":N,"deliverables":[...],"feedback_memories":[...],"surprises":[...],"next":[...]}'
    ```
10. **Autonomous session** — if the user wants to launch an autonomous session,
    hand off to `runbooks/autonomous-session.md`. The end-of-day celebration is the
    natural entry point: all branches are pushed, STATE is fresh, context is warm.
