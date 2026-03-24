# On start — conversation start trigger

Run at the start of every conversation, before the first response.

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

## 3. Housekeeping (last action on main)

If `STATE.md` is not dated today, refresh it:
  a. `gh pr list --state open` → update "Active PRs" section.
  b. `git log --oneline -5` → update "Recent" section.
  c. Commit on `main`: `housekeeping: refresh STATE YYYY-MM-DD`

This is the **only** commit allowed on main. Everything after this step
happens on a branch.

## 4. Branch and announce phase

Infer the DD phase from context, create or checkout the working branch,
then announce. **Never edit files while on main.**

| Context | Phase | Branch |
|---------|-------|--------|
| Active feature branch + open PR | `[→ Doing]` | Checkout existing branch |
| Ticket reference but no branch | `[→ Planning]` | Create `t{N}-short-description` |
| Fresh conversation, no ticket | `[→ Dreaming]` | Create `explore-{topic}` from first user message |

If the conversation turns out to be a quick question with no file edits,
the branch is harmless — delete it at session end if empty.
