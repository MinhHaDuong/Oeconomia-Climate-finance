"""Parse %ticket v1 files (magic line + RFC 822 headers + log + body).

Shared by validate_tickets.py, ready_tickets.py, archive_tickets.py.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

MAGIC_LINE = "%ticket v1"


@dataclass
class Ticket:
    """Parsed ticket with headers, log lines, and body text."""

    path: Path
    headers: dict[str, list[str]]  # key → list of values (repeatable headers)
    log_lines: list[str]
    body: str
    has_magic: bool = False
    has_log: bool = False
    has_body: bool = False

    @property
    def title(self) -> str:
        return self.headers.get("Title", [""])[0]

    @property
    def status(self) -> str:
        return self.headers.get("Status", [""])[0]

    @property
    def blocked_by(self) -> list[str]:
        return self.headers.get("Blocked-by", [])

    @property
    def filename_id(self) -> str:
        """Extract the numeric ID prefix from the filename (e.g., '0042' from '0042-add-auth.ticket')."""
        stem = self.path.stem
        parts = stem.split("-", 1)
        return parts[0] if parts else ""


def parse_ticket(path: Path) -> Ticket:
    """Parse a %ticket v1 file into a Ticket object."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    headers: dict[str, list[str]] = {}
    log_lines: list[str] = []
    body_lines: list[str] = []
    has_magic = False
    has_log = False
    has_body = False

    section = "magic"  # magic | headers | gap | log | body

    for line in lines:
        trimmed = line.strip()

        # First non-empty line must be the magic line
        if section == "magic":
            if not trimmed:
                continue
            if trimmed == MAGIC_LINE:
                has_magic = True
                section = "headers"
                continue
            # No magic line — try to parse as headers
            section = "headers"
            # Fall through

        if not has_body and trimmed == "--- log ---":
            section = "log"
            has_log = True
            continue
        if not has_body and trimmed == "--- body ---":
            section = "body"
            has_body = True
            continue

        if section == "headers":
            if not trimmed:
                section = "gap"
                continue
            m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                headers.setdefault(key, []).append(val)
        elif section == "gap":
            pass
        elif section == "log":
            if trimmed:
                log_lines.append(line)
        elif section == "body":
            body_lines.append(line)

    return Ticket(
        path=path,
        headers=headers,
        log_lines=log_lines,
        body="\n".join(body_lines),
        has_magic=has_magic,
        has_log=has_log,
        has_body=has_body,
    )


def load_tickets(directory: Path) -> list[Ticket]:
    """Load all .ticket files from a directory (non-recursive)."""
    tickets = []
    for p in sorted(directory.glob("*.ticket")):
        tickets.append(parse_ticket(p))
    return tickets
