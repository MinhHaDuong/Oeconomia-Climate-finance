---
name: ticket-ready
description: List local tickets that are ready for work (unblocked).
disable-model-invocation: false
user-invocable: true
argument-hint:
---

# List ready tickets

## Steps

1. Read all `tickets/*.erg` files.

2. For each ticket with `Status: open`:
   - Check every `Blocked-by` reference:
     - Local ID (4 digits): look up the referenced ticket's status. Ready only if `closed`.
     - `gh#N`: treat as satisfied (no network call).
     - Missing reference: warn, treat as satisfied.

3. Display ready tickets (unblocked).

## Alternative: use the CLI

```bash
tickets/tools/go/erg ready tickets/
```

With JSON output:
```bash
tickets/tools/go/erg ready tickets/ --json
```
