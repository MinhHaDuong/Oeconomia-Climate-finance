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


def ticket_age_date(ticket: Ticket) -> datetime | None:
    """Determine when the ticket was last touched.

    Uses the last log entry timestamp if available, otherwise falls back
    to the Created header date.
    """
    if ticket.log_lines:
        last = ticket.log_lines[-1].strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2}T[\d:]+Z?)", last)
        if m:
            ts = m.group(1)
            if not ts.endswith("Z"):
                ts += "Z"
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    created = ticket.headers.get("Created", [""])[0]
    m = re.match(r"(\d{4}-\d{2}-\d{2})$", created)
    if m:
        return datetime.fromisoformat(m.group(1) + "T00:00:00+00:00")

    return None


def find_archivable(
    ticket_dir: Path, days: int
) -> tuple[list[Ticket], list[Ticket], set[str]]:
    """Return (archivable, dag_protected, referenced_ids)."""
    tickets = load_tickets(ticket_dir)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Collect all IDs referenced by Blocked-by in live AND archived tickets
    referenced_ids: set[str] = set()
    all_tickets = list(tickets)
    archive_dir = ticket_dir / "archive"
    if archive_dir.is_dir():
        all_tickets.extend(load_tickets(archive_dir))
    for t in all_tickets:
        for ref in t.blocked_by:
            if not ref.startswith("gh#"):
                referenced_ids.add(ref)

    candidates = []
    for t in tickets:
        if t.status != "closed":
            continue
        last_date = ticket_age_date(t)
        if last_date is None or last_date >= cutoff:
            continue
        candidates.append(t)

    archivable = []
    dag_protected = []
    for t in candidates:
        if t.filename_id in referenced_ids:
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
            + ", ".join(t.filename_id for t in dag_protected)
        )

    if not archivable:
        print(f"Nothing to archive (threshold: {days} days).")
        return 0

    print(
        f"Will archive {len(archivable)} ticket(s): "
        + ", ".join(t.filename_id for t in archivable)
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
