"""Tests for ticket validation (tickets/tools/validate_tickets.py)."""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tickets" / "tools"))

from ticket_parser import Ticket, parse_ticket
from validate_tickets import validate_all, validate_ticket


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
    def test_parse_valid_ticket(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-auth-flow.ticket",
            """\
            Id: afg
            Title: Auth flow
            Author: claude
            Status: open
            Created: 2026-03-21

            --- log ---
            2026-03-21T10:00Z claude created

            --- body ---
            Free-form body.
            """,
        )
        assert t.id == "afg"
        assert t.title == "Auth flow"
        assert t.status == "open"
        assert t.filename_id == "afg"
        assert len(t.log_lines) == 1
        assert "Free-form body" in t.body

    def test_parse_repeatable_headers(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "x-test.ticket",
            """\
            Id: x
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: a
            Blocked-by: b

            --- log ---
            --- body ---
            """,
        )
        assert t.blocked_by == ["a", "b"]


class TestValidation:
    def test_valid_ticket_passes(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-auth-flow.ticket",
            """\
            Id: afg
            Title: Auth flow
            Author: claude
            Status: open
            Created: 2026-03-21

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert errors == []

    def test_missing_required_header(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-auth-flow.ticket",
            """\
            Id: afg
            Title: Auth flow
            Status: open
            Created: 2026-03-21

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert any("missing required header 'Author'" in e for e in errors)

    def test_id_filename_mismatch(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "xyz-something.ticket",
            """\
            Id: afg
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert any("does not match filename" in e for e in errors)

    def test_invalid_status(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-test.ticket",
            """\
            Id: afg
            Title: Test
            Author: a
            Status: invalid
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert any("invalid Status" in e for e in errors)

    def test_invalid_phase(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-test.ticket",
            """\
            Id: afg
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            X-Phase: invalid

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert any("invalid X-Phase" in e for e in errors)

    def test_blocked_by_unknown_id(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-test.ticket",
            """\
            Id: afg
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: nonexistent

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg"})
        assert any("references unknown ticket ID" in e for e in errors)

    def test_blocked_by_known_id_passes(self, tmp_ticket):
        t = _parse(
            tmp_ticket,
            "afg-test.ticket",
            """\
            Id: afg
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: xyz

            --- log ---
            --- body ---
            """,
        )
        errors = validate_ticket(t, {"afg", "xyz"})
        assert errors == []


class TestValidateAll:
    def test_duplicate_id(self, tmp_ticket):
        t1 = _parse(
            tmp_ticket,
            "afg-one.ticket",
            """\
            Id: afg
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
            "afg-two.ticket",
            """\
            Id: afg
            Title: Two
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
            """,
        )
        errors = validate_all([t1, t2])
        assert any("duplicate Id 'afg'" in e for e in errors)
        assert any("next available" in e for e in errors)

    def test_valid_collection(self, tmp_ticket):
        t1 = _parse(
            tmp_ticket,
            "afg-one.ticket",
            """\
            Id: afg
            Title: One
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: xyz

            --- log ---
            --- body ---
            """,
        )
        t2 = _parse(
            tmp_ticket,
            "xyz-two.ticket",
            """\
            Id: xyz
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


class TestExistingTickets:
    """Validate all real tickets in the repository pass."""

    def test_real_tickets_pass(self):
        from validate_tickets import validate_all
        from ticket_parser import load_tickets

        ticket_dir = Path(__file__).resolve().parent.parent / "tickets"
        if not ticket_dir.exists():
            pytest.skip("No tickets/ directory")
        tickets = load_tickets(ticket_dir)
        if not tickets:
            pytest.skip("No .ticket files found")
        errors = validate_all(tickets)
        assert errors == [], f"Validation errors:\n" + "\n".join(errors)
