# On start — conversation start trigger

Run at the start of every conversation, before the first response.

1. Load `.env` and set agent identity:
   ```bash
   set -a && source .env && set +a
   git config user.name  "$AGENT_GIT_NAME"
   git config user.email "$AGENT_GIT_EMAIL"
   export GH_TOKEN="$AGENT_GH_TOKEN"
   ```
2. Read `STATE.md` and `ROADMAP.md`.
3. If `STATE.md` is not dated today, refresh it:
   a. `gh pr list --state open` → update "Active PRs" section.
   b. `git log --oneline -5` → update "Recent" section.
   c. Sweep stale memories (follow `runbooks/memory.md`).
   d. Commit on `main`: `housekeeping: refresh STATE YYYY-MM-DD`
