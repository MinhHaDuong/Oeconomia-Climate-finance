#!/usr/bin/env python3
"""DAG-safe archival of old closed tickets.

Usage:
    python tickets/tools/archive_tickets.py [tickets/] [--days N] [--execute]

Default: dry-run. Pass --execute to actually move files and commit.
"""

import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ticket_parser import load_tickets, Ticket


DAG_HEADERS = ("Blocked-by", "X-Discovered-from", "X-Supersedes", "X-Parent")


def last_log_date(ticket: Ticket) -> datetime | None:
    """Extract the timestamp from the last log entry."""
    if not ticket.log_lines:
        return None
    # Log format: 2026-03-21T12:00Z agent event
    last = ticket.log_lines[-1].strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2}T[\d:]+Z?)", last)
    if not m:
        return None
    ts = m.group(1)
    if not ts.endswith("Z"):
        ts += "Z"
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def find_archivable(
    ticket_dir: Path, days: int
) -> tuple[list[Ticket], list[Ticket], set[str]]:
    """Return (archivable, dag_protected, referenced_ids)."""
    tickets = load_tickets(ticket_dir)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Collect all IDs referenced by DAG headers in live AND archived tickets
    referenced_ids: set[str] = set()
    all_tickets = list(tickets)
    archive_dir = ticket_dir / "archive"
    if archive_dir.is_dir():
        all_tickets.extend(load_tickets(archive_dir))
    for t in all_tickets:
        for hdr in DAG_HEADERS:
            for val in t.headers.get(hdr, []):
                referenced_ids.add(val)

    candidates = []
    for t in tickets:
        if t.status != "closed":
            continue
        last_date = last_log_date(t)
        if last_date is None or last_date >= cutoff:
            continue
        candidates.append(t)

    archivable = []
    dag_protected = []
    for t in candidates:
        if t.id in referenced_ids:
            dag_protected.append(t)
        else:
            archivable.append(t)

    return archivable, dag_protected, referenced_ids


def main() -> int:
    args = sys.argv[1:]
    execute = "--execute" in args
    args = [a for a in args if a != "--execute"]

    days = 90
    ticket_dir = Path("tickets")

    i = 0
    while i < len(args):
        if args[i].startswith("--days="):
            days = int(args[i].split("=", 1)[1])
            i += 1
        elif args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            ticket_dir = Path(args[i])
            i += 1
        else:
            i += 1

    if not ticket_dir.exists():
        print(f"Directory not found: {ticket_dir}")
        return 1

    archivable, dag_protected, _ = find_archivable(ticket_dir, days)

    if dag_protected:
        print(
            f"DAG-protected (skipping {len(dag_protected)}): "
            + ", ".join(t.id for t in dag_protected)
        )

    if not archivable:
        print(f"Nothing to archive (threshold: {days} days).")
        return 0

    print(
        f"Will archive {len(archivable)} ticket(s): "
        + ", ".join(t.id for t in archivable)
    )

    if not execute:
        print("Dry run. Pass --execute to proceed.")
        return 0

    archive_dir = ticket_dir / "archive"
    archive_dir.mkdir(exist_ok=True)

    for t in archivable:
        dest = archive_dir / t.path.name
        subprocess.run(
            ["git", "mv", str(t.path), str(dest)],
            check=True,
        )
        print(f"  moved {t.path.name}")

    msg = f"archive {len(archivable)} closed tickets (>{days} days, DAG-safe)"
    subprocess.run(["git", "commit", "-m", msg], check=True)
    print(f"Committed: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
