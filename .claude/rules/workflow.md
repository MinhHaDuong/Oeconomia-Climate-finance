# Session Start

At the beginning of every conversation:

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

**GATE — nothing below this step runs until a branch is checked out.**

Infer the Dragon Dreaming phase from context, create or checkout the working branch, then announce. The pre-commit hook blocks all commits on main.

| Context | Phase | Branch |
|---------|-------|--------|
| Fresh conversation, no ticket | `[→ Dreaming]` | Create `explore-{topic}` |
| Ticket reference but no branch | `[→ Planning]` | Create `explore-{topic}`; the `/start-ticket` skill creates the `t{N}` branch when Doing begins |
| Active feature branch + open PR | `[→ Doing]` | Checkout existing branch |

If the conversation turns out to be a quick question with no file edits, the branch is harmless — delete it at session end if empty.

# Escalation Protocol

When stuck, escalate progressively:
1. Fix direct — review feedback is straightforward.
2. Alternative approach — rethink the solution.
3. Parallel expert agents — fan-out different directions.
4. Re-ticket with diagnosis — the problem is mis-specified.
5. Stop — ask the author.

Save a feedback memory at each escalation (what failed, why). Stop if repeating yourself.

# When to Ask the Author

- You're stuck after three different approaches (including expert fan-out).
- The task requires a judgment call outside your domain docs.
- See writing rules for manuscript-specific guidance.
