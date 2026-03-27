"""Tests for archive_tickets.py — DAG-safe archival of old closed %ticket v1 files."""

import textwrap
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tickets" / "tools"))

from archive_tickets import find_archivable, ticket_age_date
from ticket_parser import parse_ticket


@pytest.fixture
def ticket_dir(tmp_path):
    def _make(**tickets):
        for name, content in tickets.items():
            (tmp_path / name).write_text(textwrap.dedent(content))
        return tmp_path
    return _make


class TestTicketAgeDate:
    def test_parses_log_timestamp(self, tmp_path):
        p = tmp_path / "0001-test.ticket"
        p.write_text(textwrap.dedent("""\
            %ticket v1
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
        dt = ticket_age_date(t)
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15

    def test_falls_back_to_created(self, tmp_path):
        p = tmp_path / "0001-nolog.ticket"
        p.write_text(textwrap.dedent("""\
            %ticket v1
            Title: No log
            Author: a
            Status: closed
            Created: 2025-06-15

            --- log ---

            --- body ---
        """))
        t = parse_ticket(p)
        dt = ticket_age_date(t)
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6

    def test_returns_none_when_no_date(self, tmp_path):
        p = tmp_path / "0001-nodate.ticket"
        p.write_text(textwrap.dedent("""\
            %ticket v1
            Title: No date
            Author: a
            Status: closed
            Created: not-a-date

            --- log ---

            --- body ---
        """))
        t = parse_ticket(p)
        assert ticket_age_date(t) is None


class TestFindArchivable:
    def test_old_closed_no_refs_archivable(self, ticket_dir):
        d = ticket_dir(**{"0001-old.ticket": """\
            %ticket v1
            Title: Old closed
            Author: a
            Status: closed
            Created: 2025-01-01

            --- log ---
            2025-01-01T10:00Z a created
            2025-01-02T10:00Z a status closed

            --- body ---
        """})
        archivable, protected, _ = find_archivable(d, days=90)
        assert len(archivable) == 1
        assert archivable[0].filename_id == "0001"
        assert len(protected) == 0

    def test_old_closed_with_ref_protected(self, ticket_dir):
        d = ticket_dir(**{
            "0001-old.ticket": """\
                %ticket v1
                Title: Old closed
                Author: a
                Status: closed
                Created: 2025-01-01

                --- log ---
                2025-01-01T10:00Z a created
                2025-01-02T10:00Z a status closed

                --- body ---
            """,
            "0002-open.ticket": """\
                %ticket v1
                Title: Open
                Author: a
                Status: open
                Created: 2026-01-01
                Blocked-by: 0001

                --- log ---
                2026-01-01T10:00Z a created

                --- body ---
            """,
        })
        archivable, protected, _ = find_archivable(d, days=90)
        assert len(archivable) == 0
        assert len(protected) == 1
        assert protected[0].filename_id == "0001"

    def test_recent_closed_not_archivable(self, ticket_dir):
        d = ticket_dir(**{"0001-recent.ticket": """\
            %ticket v1
            Title: Recent
            Author: a
            Status: closed
            Created: 2026-03-20

            --- log ---
            2026-03-20T10:00Z a created
            2026-03-21T10:00Z a status closed

            --- body ---
        """})
        archivable, _, _ = find_archivable(d, days=90)
        assert len(archivable) == 0

    def test_open_tickets_never_archivable(self, ticket_dir):
        d = ticket_dir(**{"0001-open.ticket": """\
            %ticket v1
            Title: Open
            Author: a
            Status: open
            Created: 2025-01-01

            --- log ---
            2025-01-01T10:00Z a created

            --- body ---
        """})
        archivable, _, _ = find_archivable(d, days=90)
        assert len(archivable) == 0
