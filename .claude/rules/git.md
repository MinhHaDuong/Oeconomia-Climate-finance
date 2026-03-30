# Git Discipline

- **Always work on a branch.** Branch naming: `t{N}-short-description` (Doing), `explore-{topic}` (Dreaming), or `submission/{journal}-{document}` (submission tracking). Main is read-only except for STATE housekeeping.
- **Enforced by pre-commit hook**: no commits on `main`, `CLAUDE.md` locked, no secrets, no large files (>500KB), no conflict markers.
- **`.worktreeinclude`**: auto-copies `.env` and `.dvc/config.local` into worktrees created by `EnterWorktree`.
- **Git hooks** live in `hooks/`. After cloning: `make setup`. Agents: set automatically at session start.
- **Agent identity**: machine user `HDMX-coding-agent`. Credentials (`AGENT_GH_TOKEN`, `AGENT_GIT_NAME`, `AGENT_GIT_EMAIL`) from `.env`.
- **One change per commit.** Message explains *why this change and not another*: alternatives considered, local design choices made.
- **Merge commits**: strategic-level detail — architecture decisions, cross-file impacts, residual debt. Feature merges go through PRs; chores merge locally via short-lived branch + fast-forward.
- **Git is the project's long-term memory.** Top-level files reflect *now* — history lives in `git log`.
- **Every conversation runs in a worktree** — `EnterWorktree` at session start, `ExitWorktree` at end. All worktrees are throwaway; branches hold durable state.
- **Create PR** for each ticket to review changes before merging.
- **Submission branches** are protected: no merges (cherry-pick only), no deletion, no force-push.
