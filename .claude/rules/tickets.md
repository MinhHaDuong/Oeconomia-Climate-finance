---
globs: ["tickets/**/*.erg"]
---

# Tickets

Use `%erg v1` format. Full spec: `tickets/FORMAT.md`. Pre-commit validator enforces structure.

Key points: 4-digit ID from filename, `--- log ---` and `--- body ---` separators required,
claim via `.git/ticket-wip/{ID}.wip`, ready = open + unblocked + unclaimed.

Postel's Law: strict on write, tolerant on read. Parse any input format, emit clean `%erg v1`.
