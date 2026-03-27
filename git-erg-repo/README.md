# git-erg

Agent-native local ticket system for git worktree coordination.

- **File-based**: plain text `.erg` files committed to git
- **Offline-first**: no network, no API, no database
- **Zero dependencies**: single Go binary, shell tests
- **Agent-friendly by design**: the spec is the interface, the binary is the guardrail

## Quick start

```bash
# Build the validator
make build

# Create a ticket (or just write the file — agents do)
cat > tickets/0001-add-auth.erg <<'EOF'
%erg v1
Title: Add authentication flow
Status: open
Created: 2026-03-27
Author: claude

--- log ---
2026-03-27T10:00Z claude created

--- body ---
## Context
Need auth before shipping the API.
EOF

# Validate
erg validate tickets/

# List ready tickets
erg ready tickets/
```

## Format

See [rules/tickets.md](rules/tickets.md) for the complete `%erg v1` specification.

## For Claude Code users

Copy `claude/` into your project's `.claude/` directory to get skills:
`/ticket-new`, `/ticket-claim`, `/ticket-close`, `/ticket-release`, `/ticket-ready`

Copy `rules/tickets.md` into `.claude/rules/`.

## For other agents

Read `rules/tickets.md`. That's the complete spec. Write `.erg` files directly.
The Go binary validates on commit — your agent doesn't need it to operate.

## Design

See [docs/pep-erg-v1.md](docs/pep-erg-v1.md) for design rationale, alternatives
explored, and architectural decisions.

## License

MIT
