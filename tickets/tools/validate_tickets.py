#!/usr/bin/env python3
"""Validate .ticket files: required headers, unique IDs, valid references.

Usage:
    python tickets/tools/validate_tickets.py [tickets/]
    python tickets/tools/validate_tickets.py tickets/foo.ticket tickets/bar.ticket

Exit 0 on success, exit 1 with diagnostics on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ticket_parser import Ticket, load_tickets, parse_ticket

REQUIRED_HEADERS = ["Id", "Title", "Author", "Status", "Created"]
VALID_STATUSES = {"open", "doing", "closed", "pending"}
VALID_PHASES = {"dreaming", "planning", "doing", "celebrating"}


def validate_ticket(ticket: Ticket, all_ids: set[str]) -> list[str]:
    """Return list of error strings for a single ticket."""
    errors: list[str] = []
    path = ticket.path.name

    # Required headers
    for hdr in REQUIRED_HEADERS:
        if hdr not in ticket.headers:
            errors.append(f"{path}: missing required header '{hdr}'")

    # Id/filename consistency
    if ticket.id and ticket.filename_id != ticket.id:
        errors.append(
            f"{path}: Id '{ticket.id}' does not match filename "
            f"prefix '{ticket.filename_id}'"
        )

    # Valid Status
    if ticket.status and ticket.status not in VALID_STATUSES:
        errors.append(
            f"{path}: invalid Status '{ticket.status}' "
            f"(expected one of: {', '.join(sorted(VALID_STATUSES))})"
        )

    # Valid X-Phase
    phases = ticket.headers.get("X-Phase", [])
    for phase in phases:
        if phase not in VALID_PHASES:
            errors.append(
                f"{path}: invalid X-Phase '{phase}' "
                f"(expected one of: {', '.join(sorted(VALID_PHASES))})"
            )

    # Blocked-by references exist
    for ref in ticket.blocked_by:
        if ref not in all_ids:
            errors.append(
                f"{path}: Blocked-by '{ref}' references unknown ticket ID"
            )

    return errors


def detect_cycles(tickets: list[Ticket]) -> list[str]:
    """Detect cycles in the Blocked-by dependency graph via DFS."""
    errors = []
    adj: dict[str, list[str]] = {}
    for t in tickets:
        if t.id:
            adj[t.id] = list(t.blocked_by)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in adj}

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj.get(node, []):
            if neighbor not in color:
                continue  # reference to unknown ID, handled elsewhere
            if color[neighbor] == GRAY:
                # Found a cycle — extract it from path
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                errors.append(
                    f"dependency cycle: {' -> '.join(cycle)}"
                )
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for tid in adj:
        if color[tid] == WHITE:
            dfs(tid, [])

    return errors


def validate_all(
    tickets: list[Ticket], extra_ids: set[str] | None = None
) -> list[str]:
    """Validate a collection of tickets. Returns all errors.

    extra_ids: additional known IDs (e.g., from archived tickets) that
    are valid Blocked-by targets but are not themselves validated.
    """
    errors: list[str] = []

    # Collect all IDs and check for duplicates
    id_to_files: dict[str, list[str]] = {}
    for t in tickets:
        if t.id:
            id_to_files.setdefault(t.id, []).append(t.path.name)

    for tid, files in id_to_files.items():
        if len(files) > 1:
            # Suggest next available suffix
            base = tid.rstrip("0123456789")
            existing_nums = set()
            for other_id in id_to_files:
                if other_id == base:
                    existing_nums.add(1)
                elif other_id.startswith(base):
                    suffix = other_id[len(base):]
                    if suffix.isdigit():
                        existing_nums.add(int(suffix))
            next_num = max(existing_nums, default=1) + 1
            errors.append(
                f"duplicate Id '{tid}' in: {', '.join(files)} "
                f"-- next available: {base}{next_num}"
            )

    all_ids = set(id_to_files.keys())
    if extra_ids:
        all_ids |= extra_ids

    # Per-ticket validation
    for t in tickets:
        errors.extend(validate_ticket(t, all_ids))

    errors.extend(detect_cycles(tickets))

    return errors


def main() -> int:
    args = sys.argv[1:]

    if not args:
        # Default: validate tickets/ directory
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

    # Load archived ticket IDs as valid Blocked-by targets
    extra_ids: set[str] = set()
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            archive_dir = p / "archive"
            if archive_dir.is_dir():
                for at in load_tickets(archive_dir):
                    if at.id:
                        extra_ids.add(at.id)

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
