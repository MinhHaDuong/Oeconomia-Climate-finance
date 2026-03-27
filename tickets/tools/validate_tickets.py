#!/usr/bin/env python3
"""Validate %ticket v1 files: magic line, closed headers, unique IDs, valid references.

Usage:
    python tickets/tools/validate_tickets.py [tickets/]
    python tickets/tools/validate_tickets.py tickets/foo.ticket tickets/bar.ticket

Exit 0 on success, exit 1 with diagnostics on failure.
"""

import re
import sys
from pathlib import Path

from ticket_parser import Ticket, load_tickets, parse_ticket

REQUIRED_HEADERS = ["Title", "Status", "Created", "Author"]
VALID_HEADERS = {"Title", "Status", "Created", "Author", "Blocked-by"}
VALID_STATUSES = {"open", "doing", "closed", "pending"}
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FILENAME_RE = re.compile(r"^\d{4}-[a-z0-9]+(-[a-z0-9]+)*\.ticket$")
_LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z\s+\S+\s+\S+")


def validate_ticket(ticket: Ticket, all_ids: set[str]) -> list[str]:
    """Return list of error strings for a single ticket."""
    errors: list[str] = []
    path = ticket.path.name

    # Rule 1: magic first line
    if not ticket.has_magic:
        errors.append(f"{path}: missing magic first line '%ticket v1'")

    # Rule 2: required headers
    for hdr in REQUIRED_HEADERS:
        if hdr not in ticket.headers:
            errors.append(f"{path}: missing required header '{hdr}'")

    # Rule 3: no unknown headers
    for key in ticket.headers:
        if key not in VALID_HEADERS:
            errors.append(
                f"{path}: unknown header '{key}' (not in v1 closed set)"
            )

    # Rule 4: valid Status
    if ticket.status and ticket.status not in VALID_STATUSES:
        errors.append(
            f"{path}: invalid Status '{ticket.status}' "
            f"(expected one of: {', '.join(sorted(VALID_STATUSES))})"
        )

    # Rule 5: Created must be ISO date
    created = ticket.headers.get("Created", [""])[0]
    if created and not _ISO_DATE_RE.match(created):
        errors.append(
            f"{path}: Created '{created}' is not a valid ISO date (YYYY-MM-DD)"
        )

    # Rule 6: filename matches NNNN-slug.ticket
    if not _FILENAME_RE.match(path):
        errors.append(
            f"{path}: filename does not match NNNN-slug.ticket pattern"
        )

    # Rule 8: Blocked-by references exist
    for ref in ticket.blocked_by:
        if ref.startswith("gh#"):
            continue  # GitHub issue reference — not validated locally
        if ref not in all_ids:
            errors.append(
                f"{path}: Blocked-by '{ref}' references unknown ticket ID"
            )

    # Rule 10: log lines match format
    for line in ticket.log_lines:
        trimmed = line.strip()
        if trimmed and not _LOG_LINE_RE.match(trimmed):
            errors.append(f"{path}: malformed log line: {trimmed}")

    # Rule 11: both separators present
    if not ticket.has_log:
        errors.append(f"{path}: missing '--- log ---' separator")
    if not ticket.has_body:
        errors.append(f"{path}: missing '--- body ---' separator")

    return errors


def detect_cycles(tickets: list[Ticket]) -> list[str]:
    """Detect cycles in the Blocked-by dependency graph via DFS."""
    errors = []
    adj: dict[str, list[str]] = {}
    for t in tickets:
        tid = t.filename_id
        if tid:
            adj[tid] = [r for r in t.blocked_by if not r.startswith("gh#")]

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in adj}

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                errors.append(
                    f"dependency cycle: {' -> '.join(cycle)}"
                )
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for tid in sorted(adj):
        if color[tid] == WHITE:
            dfs(tid, [])

    return errors


def validate_all(
    tickets: list[Ticket], extra_ids: set[str] | None = None
) -> list[str]:
    """Validate a collection of tickets. Returns all errors."""
    errors: list[str] = []

    # Collect all IDs and check for duplicates
    id_to_files: dict[str, list[str]] = {}
    for t in tickets:
        tid = t.filename_id
        if tid:
            id_to_files.setdefault(tid, []).append(t.path.name)

    for tid, files in sorted(id_to_files.items()):
        if len(files) > 1:
            errors.append(
                f"duplicate ID '{tid}' in: {', '.join(files)}"
            )

    # Check for collisions with archived ticket IDs
    if extra_ids:
        for tid in id_to_files:
            if tid in extra_ids:
                errors.append(
                    f"ID '{tid}' in {', '.join(id_to_files[tid])} "
                    f"collides with an archived ticket"
                )

    all_ids = set(id_to_files.keys())
    if extra_ids:
        all_ids |= extra_ids

    for t in tickets:
        errors.extend(validate_ticket(t, all_ids))

    errors.extend(detect_cycles(tickets))

    return errors


def main() -> int:
    args = sys.argv[1:]

    if not args:
        args = ["tickets/"]

    tickets: list[Ticket] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            tickets.extend(load_tickets(p))
        elif p.is_file() and p.suffix == ".ticket":
            tickets.append(parse_ticket(p))
        else:
            print(f"WARNING: skipping {arg} (not a .ticket file or directory)")

    if not tickets:
        print("No .ticket files found.")
        return 0

    extra_ids: set[str] = set()
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            archive_dir = p / "archive"
            if archive_dir.is_dir():
                for at in load_tickets(archive_dir):
                    tid = at.filename_id
                    if tid:
                        extra_ids.add(tid)

    errors = validate_all(tickets, extra_ids=extra_ids)

    if errors:
        print(f"TICKET VALIDATION FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(f"TICKET VALIDATION: PASS ({len(tickets)} tickets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
