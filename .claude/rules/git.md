# Git Discipline (project-specific)

Generic git discipline is in `~/.claude/rules/git.md`. This file adds project-specific conventions.

- **Branch naming**: `t{N}-short-description` (Execute), `explore-{topic}` (Imagine), or `submission/{journal}-{document}` (submission tracking).
- **Enforced by pre-commit hook** — see `hooks/pre-commit` for specifics.
- **`.worktreeinclude`**: auto-copies `.env` and `.dvc/config.local` into worktrees created by `EnterWorktree`.
- **Git hooks** live in `hooks/`. After cloning: `make setup`. Agents: set automatically at session start.
- **Agent identity**: machine user `HDMX-coding-agent`. Credentials (`AGENT_GH_TOKEN`, `AGENT_GIT_NAME`, `AGENT_GIT_EMAIL`) from `.env`.
- **Submission branches** are protected: no merges (cherry-pick only), no deletion, no force-push.
