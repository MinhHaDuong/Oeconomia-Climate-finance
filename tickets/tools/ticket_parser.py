"""Parse .ticket files (RFC 822 headers + log + body).

Shared by validate_tickets.py, ready_tickets.py, archive_tickets.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Ticket:
    """Parsed ticket with headers, log lines, and body text."""

    path: Path
    headers: dict[str, list[str]]  # key → list of values (repeatable headers)
    log_lines: list[str]
    body: str

    # Convenience accessors for required scalar headers
    @property
    def id(self) -> str:
        return self.headers.get("Id", [""])[0]

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
        """Extract the ID portion from the filename ({id}-{slug}.ticket)."""
        stem = self.path.stem  # e.g. "afg-auth-flow-gates"
        parts = stem.split("-", 1)
        return parts[0] if parts else ""


def parse_ticket(path: Path) -> Ticket:
    """Parse a .ticket file into a Ticket object.

    Format:
      RFC 822 headers (Key: value, one per line)
      <blank line>
      --- log ---
      log entries...
      --- body ---
      free-form body...
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    headers: dict[str, list[str]] = {}
    log_lines: list[str] = []
    body_lines: list[str] = []

    section = "headers"  # headers | log | body
    log_seen = False
    body_seen = False

    for line in lines:
        if not body_seen and line.strip() == "--- log ---":
            section = "log"
            log_seen = True
            continue
        if not body_seen and line.strip() == "--- body ---":
            section = "body"
            body_seen = True
            continue

        if section == "headers":
            if not line.strip():
                continue  # skip blank lines in header area
            m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                headers.setdefault(key, []).append(val)
        elif section == "log":
            if line.strip():
                log_lines.append(line)
        elif section == "body":
            body_lines.append(line)

    return Ticket(
        path=path,
        headers=headers,
        log_lines=log_lines,
        body="\n".join(body_lines),
    )


def load_tickets(directory: Path) -> list[Ticket]:
    """Load all .ticket files from a directory (non-recursive)."""
    tickets = []
    for p in sorted(directory.glob("*.ticket")):
        tickets.append(parse_ticket(p))
    return tickets
