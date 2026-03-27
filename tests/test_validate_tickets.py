"""Tests for %ticket v1 validation."""

import textwrap
from pathlib import Path

import pytest

# Add ticket tools to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tickets" / "tools"))

from ticket_parser import Ticket, parse_ticket, load_tickets
from validate_tickets import detect_cycles, validate_all, validate_ticket


@pytest.fixture
def tmp_ticket(tmp_path):
    """Factory for creating temporary .ticket files."""

    def _make(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(textwrap.dedent(content))
        return p

    return _make


def _parse(tmp_ticket, name: str, content: str) -> Ticket:
    path = tmp_ticket(name, content)
    return parse_ticket(path)


class TestParser:
    def test_parse_valid_v1_ticket(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-auth-flow.ticket",
            """\
            %ticket v1
            Title: Add auth flow
            Author: claude
            Status: open
            Created: 2026-03-21

            --- log ---
            2026-03-21T10:00Z claude created

            --- body ---
            Free-form body.
            """,
        )
        assert t.has_magic
        assert t.title == "Add auth flow"
        assert t.status == "open"
        assert t.filename_id == "0001"
        assert len(t.log_lines) == 1
        assert "Free-form body" in t.body

    def test_magic_line_required(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            Title: No magic
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        assert not t.has_magic

    def test_blank_line_ends_headers(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test

            Status: open
            Created: 2026-01-01
            Author: a

            --- log ---
            --- body ---
            """,
        )
        # Status and Created are after the blank line, so NOT parsed as headers
        assert "Status" not in t.headers
        assert "Created" not in t.headers

    def test_parse_repeatable_headers(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: 0002
            Blocked-by: 0003

            --- log ---
            --- body ---
            """,
        )
        assert t.blocked_by == ["0002", "0003"]

    def test_separators_tracked(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        assert t.has_log
        assert t.has_body

    def test_missing_separators(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            """,
        )
        assert not t.has_log
        assert not t.has_body


class TestValidation:
    def test_valid_ticket_passes(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-auth-flow.ticket",
            """\
            %ticket v1
            Title: Auth flow
            Author: claude
            Status: open
            Created: 2026-03-21

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert errors == []

    def test_missing_magic_line(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("magic first line" in e for e in errors)

    def test_missing_required_header(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("missing required header 'Author'" in e for e in errors)

    def test_unknown_header_rejected(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            X-Phase: dreaming

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("unknown header 'X-Phase'" in e for e in errors)

    def test_invalid_status(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: invalid
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("invalid Status" in e for e in errors)

    def test_pending_status_valid(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: pending
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert not any("invalid Status" in e for e in errors)

    def test_invalid_created_date(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: not-a-date

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("not a valid ISO date" in e for e in errors)

    def test_bad_filename_pattern(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-auth-flow.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert any("NNNN-slug.ticket pattern" in e for e in errors)

    def test_blocked_by_unknown_id(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: 9999

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("references unknown ticket ID" in e for e in errors)

    def test_blocked_by_github_issue_passes(self, tmp_ticket):
        """gh#N references are not validated locally."""
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: gh#435

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert not any("unknown ticket ID" in e for e in errors)

    def test_malformed_log_line(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            this is not a valid log line

            --- body ---
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("malformed log line" in e for e in errors)

    def test_missing_separators(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            """,
        )
        errors = validate_ticket(t, {"0001"})
        assert any("--- log ---" in e for e in errors)
        assert any("--- body ---" in e for e in errors)


class TestValidateAll:
    def test_duplicate_id(self, tmp_ticket):
        t1 = _parse(
            tmp_ticket,
            "0001-one.ticket",
            """\
            %ticket v1
            Title: One
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        t2 = _parse(
            tmp_ticket,
            "0001-two.ticket",
            """\
            %ticket v1
            Title: Two
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_all([t1, t2])
        assert any("duplicate ID '0001'" in e for e in errors)

    def test_valid_collection(self, tmp_ticket):
        t1 = _parse(
            tmp_ticket,
            "0001-one.ticket",
            """\
            %ticket v1
            Title: One
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: 0002

            --- log ---
            --- body ---
            """,
        )
        t2 = _parse(
            tmp_ticket,
            "0002-two.ticket",
            """\
            %ticket v1
            Title: Two
            Author: a
            Status: closed
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_all([t1, t2])
        assert errors == []


class TestCycleDetection:
    def test_simple_cycle(self, tmp_ticket):
        t1 = _parse(tmp_ticket, "0001-one.ticket", """\
            %ticket v1
            Title: One
            Author: x
            Status: open
            Created: 2026-01-01
            Blocked-by: 0002

            --- log ---
            --- body ---
        """)
        t2 = _parse(tmp_ticket, "0002-two.ticket", """\
            %ticket v1
            Title: Two
            Author: x
            Status: open
            Created: 2026-01-01
            Blocked-by: 0001

            --- log ---
            --- body ---
        """)
        errors = validate_all([t1, t2])
        assert any("dependency cycle" in e for e in errors)

    def test_no_cycle(self, tmp_ticket):
        t1 = _parse(tmp_ticket, "0001-one.ticket", """\
            %ticket v1
            Title: One
            Author: x
            Status: open
            Created: 2026-01-01
            Blocked-by: 0002

            --- log ---
            --- body ---
        """)
        t2 = _parse(tmp_ticket, "0002-two.ticket", """\
            %ticket v1
            Title: Two
            Author: x
            Status: closed
            Created: 2026-01-01

            --- log ---
            --- body ---
        """)
        errors = validate_all([t1, t2])
        assert not any("cycle" in e for e in errors)


class TestExtraIds:
    def test_blocked_by_archived_id_passes(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: 0099

            --- log ---
            --- body ---
            """,
        )
        errors = validate_all([t], extra_ids={"0099"})
        assert not any("unknown ticket ID" in e for e in errors)

    def test_live_id_collides_with_archived(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "0001-test.ticket",
            """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_all([t], extra_ids={"0001"})
        assert any("collides with an archived ticket" in e for e in errors)


class TestExistingTickets:
    """Validate all real tickets in the repository pass."""

    def test_real_tickets_pass(self):
        ticket_dir = Path(__file__).resolve().parent.parent / "tickets"
        if not ticket_dir.exists():
            pytest.skip("No tickets/ directory")
        tickets = load_tickets(ticket_dir)
        if not tickets:
            pytest.skip("No .ticket files found")
        extra_ids: set[str] = set()
        archive_dir = ticket_dir / "archive"
        if archive_dir.is_dir():
            for at in load_tickets(archive_dir):
                tid = at.filename_id
                if tid:
                    extra_ids.add(tid)
        errors = validate_all(tickets, extra_ids=extra_ids)
        assert errors == [], f"Validation errors:\n" + "\n".join(errors)
