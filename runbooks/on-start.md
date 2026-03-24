# On start — conversation start trigger

Runs after the user's first message, before the agent's first response.

## 1. Setup

Load `.env`, set agent identity, and activate hooks:
```bash
set -a && source .env && set +a
git config user.name  "$AGENT_GIT_NAME"
git config user.email "$AGENT_GIT_EMAIL"
git config core.hooksPath hooks
export GH_TOKEN="$AGENT_GH_TOKEN"
```

## 2. Orient

Read `STATE.md` and `ROADMAP.md`.

## 3. Branch and announce phase

Infer the DD phase from context, create or checkout the working branch,
then announce. **Never edit files while on main** — the pre-commit hook
blocks all commits on main, no exceptions.

| Context | Phase | Branch |
|---------|-------|--------|
| Active feature branch + open PR | `[→ Doing]` | Checkout existing branch |
| Ticket reference but no branch | `[→ Planning]` | Create `explore-{topic}`; `start-ticket` creates the `t{N}` branch when Doing begins |
| Fresh conversation, no ticket | `[→ Dreaming]` | Create `explore-{topic}` (name inferred from user's opening message) |

If the conversation turns out to be a quick question with no file edits,
the branch is harmless — delete it at session end if empty.

## 4. Housekeeping (first commit on the branch)

If `STATE.md` is not dated today, refresh it:
  a. `gh pr list --state open` → update "Active PRs" section.
  b. `git log --oneline -5` → update "Recent" section.
  c. Commit on the branch: `housekeeping: refresh STATE YYYY-MM-DD`

This merges to main with the rest of the conversation's work.
