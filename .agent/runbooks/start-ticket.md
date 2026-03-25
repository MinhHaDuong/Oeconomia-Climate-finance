# Start ticket — begin work on an issue

When this trigger runs, the agent is about to start implementing a ticket.

## Steps

1. **Read the ticket.**
   - Local ticket: read `tickets/{id}-{slug}.ticket`.
   - Forge ticket (`Coordination: gh#N`): `gh issue view N --json title,body`.
2. Check the **Exit criteria** section (or body). If unclear, ask the author before writing code.
3. Create a worktree and branch:
   ```bash
   git worktree add ../t{N}-{slug} -b t{N}-{slug}
   ```
   Where N is the ticket number (forge issue number for `Coordination: gh#N`, or a sequential local number).
4. **Claim the ticket** — set `Status: doing` in the header, append a log entry (`{ISO-timestamp} {agent-id} status doing`), and commit immediately. This makes the claim visible to other agents across worktrees.
5. **Signal work-in-progress** — create a `.wip` file visible to all local worktrees:
   ```bash
   wip_dir="$(git rev-parse --git-common-dir)/ticket-wip"
   mkdir -p "$wip_dir"
   echo "${AGENT_GIT_NAME} $(date -u +%Y-%m-%dT%H:%MZ)" > "$wip_dir/{ticket-id}.wip"
   ```
   This is a courtesy signal, not a lock. `make ticket-ready` shows it. If another agent sees it, they may skip the ticket — or ignore it and proceed.
6. Read the files listed in **Relevant files** (if any).
7. Write the first test from the **Test** section of the ticket.
8. Run `make check-fast` — confirm the test fails (Red).
9. `[Planning → Doing]` — announce the transition, then begin: Red → Green → Refactor.
10. Create the PR.
11. Review according to the runbook.
12. Fix, addressing all comments regardless of their apparent severity.
13. Repeat 11–12 up to 3 times. If still not clean, escalate (see AGENTS.md).
