# Session Start

At the beginning of every conversation:

## 1. Setup

Load `.env`, set agent identity, and activate hooks. Each line is a **separate Bash call** (compound `&&` chains bypass permission patterns):
```bash
set -a; source .env; set +a
```
```bash
git config user.name  "$AGENT_GIT_NAME"
```
```bash
git config user.email "$AGENT_GIT_EMAIL"
```
```bash
git config core.hooksPath hooks
```
```bash
export GH_TOKEN="$AGENT_GH_TOKEN"
```

## 2. Orient

Read `STATE.md` and `ROADMAP.md`.

## 3. Isolate and announce phase

**GATE — nothing below this step runs until the worktree is entered.**

Every conversation runs in its own worktree. Call `EnterWorktree` with a descriptive name, then checkout the right branch and announce the phase. This ensures parallel conversations never interfere with each other.

| Context | Worktree name | Then | Phase |
|---------|---------------|------|-------|
| Fresh conversation, no ticket | `explore-{topic}` | Create branch `explore-{topic}` | `[→ Dreaming]` |
| Ticket reference but no branch | `explore-{topic}` | Create branch `explore-{topic}` | `[→ Planning]` |
| `/start-ticket N` | `t{N}` | Create or checkout branch `t{N}-short-description` | `[→ Doing]` |
| Active feature branch + open PR | `t{N}` | Checkout existing branch | `[→ Doing]` |
| PR review | `review-{N}` | Checkout PR branch | read-only |

After `EnterWorktree`, run `git switch <branch>` (or `git switch -c <branch>`) to land on the correct branch. The worktree is throwaway — all durable state lives in branches.

`.worktreeinclude` auto-copies `.env` and `.dvc/config.local` into the worktree.

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
