"""Tests for archive_tickets.py — DAG-safe archival of old closed tickets."""

import textwrap
from pathlib import Path

import pytest

from archive_tickets import find_archivable, last_log_date
from ticket_parser import parse_ticket


@pytest.fixture
def ticket_dir(tmp_path):
    """Factory for creating a tmp directory with .ticket files."""

    def _make(**tickets):
        for name, content in tickets.items():
            (tmp_path / name).write_text(textwrap.dedent(content))
        return tmp_path

    return _make


class TestLastLogDate:
    def test_parses_timestamp(self, tmp_path):
        p = tmp_path / "x-test.ticket"
        p.write_text(textwrap.dedent("""\
            Id: x
            Title: Test
            Author: a
            Status: closed
            Created: 2026-01-01

            --- log ---
            2026-01-01T10:00Z a created
            2026-01-15T14:00Z a status closed

            --- body ---
        """))
        t = parse_ticket(p)
        dt = last_log_date(t)
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15


class TestFindArchivable:
    def test_old_closed_no_refs_archivable(self, ticket_dir):
        d = ticket_dir(
            **{
                "x-old.ticket": """\
                    Id: x
                    Title: Old closed
                    Author: a
                    Status: closed
                    Created: 2025-01-01

                    --- log ---
                    2025-01-01T10:00Z a created
                    2025-01-02T10:00Z a status closed

                    --- body ---
                """
            }
        )
        archivable, protected, _ = find_archivable(d, days=90)
        assert len(archivable) == 1
        assert archivable[0].id == "x"
        assert len(protected) == 0

    def test_old_closed_with_ref_protected(self, ticket_dir):
        d = ticket_dir(
            **{
                "x-old.ticket": """\
                    Id: x
                    Title: Old closed
                    Author: a
                    Status: closed
                    Created: 2025-01-01

                    --- log ---
                    2025-01-01T10:00Z a created
                    2025-01-02T10:00Z a status closed

                    --- body ---
                """,
                "y-open.ticket": """\
                    Id: y
                    Title: Open
                    Author: a
                    Status: open
                    Created: 2026-01-01
                    Blocked-by: x

                    --- log ---
                    2026-01-01T10:00Z a created

                    --- body ---
                """,
            }
        )
        archivable, protected, _ = find_archivable(d, days=90)
        assert len(archivable) == 0
        assert len(protected) == 1
        assert protected[0].id == "x"

    def test_recent_closed_not_archivable(self, ticket_dir):
        d = ticket_dir(
            **{
                "x-recent.ticket": """\
                    Id: x
                    Title: Recent
                    Author: a
                    Status: closed
                    Created: 2026-03-20

                    --- log ---
                    2026-03-20T10:00Z a created
                    2026-03-21T10:00Z a status closed

                    --- body ---
                """
            }
        )
        archivable, protected, _ = find_archivable(d, days=90)
        assert len(archivable) == 0

    def test_x_discovered_from_protects(self, ticket_dir):
        d = ticket_dir(
            **{
                "x-old.ticket": """\
                    Id: x
                    Title: Old
                    Author: a
                    Status: closed
                    Created: 2025-01-01

                    --- log ---
                    2025-01-01T10:00Z a created
                    2025-01-02T10:00Z a status closed

                    --- body ---
                """,
                "y-derived.ticket": """\
                    Id: y
                    Title: Derived
                    Author: a
                    Status: open
                    Created: 2026-01-01
                    X-Discovered-from: x

                    --- log ---
                    2026-01-01T10:00Z a created

                    --- body ---
                """,
            }
        )
        archivable, protected, _ = find_archivable(d, days=90)
        assert len(archivable) == 0
        assert len(protected) == 1

    def test_open_tickets_never_archivable(self, ticket_dir):
        d = ticket_dir(
            **{
                "x-open.ticket": """\
                    Id: x
                    Title: Open
                    Author: a
                    Status: open
                    Created: 2025-01-01

                    --- log ---
                    2025-01-01T10:00Z a created

                    --- body ---
                """
            }
        )
        archivable, _, _ = find_archivable(d, days=90)
        assert len(archivable) == 0
