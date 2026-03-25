#!/usr/bin/env python3
"""Find open tickets whose blockers are all resolved.

Usage:
    python tickets/tools/ready_tickets.py [tickets/]
    python tickets/tools/ready_tickets.py --json

A ticket is "ready" when:
  - Status is open (not doing, not closed)
  - Every Blocked-by reference points to a closed ticket (or doesn't exist)
"""

import json
import subprocess
import sys
from pathlib import Path

from ticket_parser import load_tickets


def _wip_dir() -> Path | None:
    """Return the shared .git/ticket-wip/ dir, or None outside a git repo."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return Path(r.stdout.strip()) / "ticket-wip"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _load_wip(wip_dir: Path | None) -> dict[str, str]:
    """Return {ticket_id: wip_line} for active .wip files."""
    if wip_dir is None or not wip_dir.is_dir():
        return {}
    wip = {}
    for f in wip_dir.glob("*.wip"):
        tid = f.stem
        wip[tid] = f.read_text().strip()
    return wip


def find_ready(ticket_dir: Path) -> tuple[list[dict], list[str], int, int]:
    """Return (ready_tickets, warnings, total_count, open_count)."""
    tickets = load_tickets(ticket_dir)
    status_by_id = {t.id: t.status for t in tickets}
    warnings: list[str] = []
    ready = []
    open_count = 0

    for t in tickets:
        if t.status != "open":
            continue
        open_count += 1

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

    return ready, warnings, len(tickets), open_count


def main() -> int:
    args = sys.argv[1:]
    use_json = "--json" in args
    args = [a for a in args if a != "--json"]

    ticket_dir = Path(args[0]) if args else Path("tickets")

    if not ticket_dir.exists():
        print(f"Directory not found: {ticket_dir}")
        return 1

    ready, warnings, total, open_count = find_ready(ticket_dir)
    wip = _load_wip(_wip_dir())

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if use_json:
        # Annotate with wip info if present
        for r in ready:
            if r["id"] in wip:
                r["wip"] = wip[r["id"]]
        print(json.dumps(ready, indent=2))
    else:
        if not ready:
            if total == 0:
                print("No tickets found.")
            elif open_count == 0:
                print(f"All {total} tickets are closed.")
            else:
                print(f"{open_count} open tickets, all blocked.")
        else:
            print(f"Ready tickets ({len(ready)}):")
            for r in ready:
                suffix = f"  (wip: {wip[r['id']]})" if r["id"] in wip else ""
                print(f"  {r['id']:<8s} {r['file']:<40s} {r['title']}{suffix}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
