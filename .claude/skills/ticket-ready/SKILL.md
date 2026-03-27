---
name: ticket-ready
description: List local tickets that are ready for work (unblocked, unclaimed).
disable-model-invocation: false
user-invocable: true
argument-hint:
---

# List ready tickets

## Steps

1. Read all `tickets/*.ticket` files.

2. For each ticket with `Status: open`:
   - Check every `Blocked-by` reference:
     - Local ID (4 digits): look up the referenced ticket's status. Ready only if `closed`.
     - `gh#N`: treat as satisfied (no network call).
     - Missing reference: warn, treat as satisfied.
   - Check for `.wip` claim:
     ```bash
     wip_dir="$(git rev-parse --git-common-dir)/ticket-wip"
     ls "$wip_dir"/*.wip 2>/dev/null
     ```

3. Display ready tickets (unblocked + unclaimed).

## Alternative: use the CLI

```bash
make ticket-ready
```

Or with JSON output:
```bash
PYTHONPATH=tickets/tools python3 tickets/tools/ready_tickets.py --json
```
