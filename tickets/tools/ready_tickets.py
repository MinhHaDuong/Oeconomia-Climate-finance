#!/usr/bin/env python3
"""Find open tickets whose blockers are all resolved.

Usage:
    python tickets/tools/ready_tickets.py [tickets/]
    python tickets/tools/ready_tickets.py --json

A ticket is "ready" when:
  - Status is open (not doing, not closed)
  - Every Blocked-by reference points to a closed ticket (or doesn't exist)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ticket_parser import load_tickets


def find_ready(ticket_dir: Path) -> tuple[list[dict], list[str]]:
    """Return (ready_tickets, warnings)."""
    tickets = load_tickets(ticket_dir)
    status_by_id = {t.id: t.status for t in tickets}
    warnings: list[str] = []
    ready = []

    for t in tickets:
        if t.status != "open":
            continue

        blocked = False
        for ref in t.blocked_by:
            ref_status = status_by_id.get(ref)
            if ref_status is None:
                warnings.append(
                    f"{t.path.name}: Blocked-by '{ref}' not found (treating as satisfied)"
                )
            elif ref_status != "closed":
                blocked = True
                break

        if not blocked:
            ready.append({"id": t.id, "title": t.title, "file": t.path.name})

    return ready, warnings


def main() -> int:
    args = sys.argv[1:]
    use_json = "--json" in args
    args = [a for a in args if a != "--json"]

    ticket_dir = Path(args[0]) if args else Path("tickets")

    if not ticket_dir.exists():
        print(f"Directory not found: {ticket_dir}")
        return 1

    ready, warnings = find_ready(ticket_dir)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if use_json:
        print(json.dumps(ready, indent=2))
    else:
        if not ready:
            print("No ready tickets.")
        else:
            print(f"Ready tickets ({len(ready)}):")
            for r in ready:
                print(f"  {r['id']:8s} {r['title']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
