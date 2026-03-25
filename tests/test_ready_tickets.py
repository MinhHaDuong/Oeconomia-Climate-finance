"""Tests for ready_tickets.py — find unblocked open tickets."""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from ready_tickets import find_ready, _load_wip


@pytest.fixture
def ticket_dir(tmp_path):
    """Factory for creating a tmp directory with .ticket files."""

    def _make(**tickets):
        """tickets: name -> content mapping."""
        for name, content in tickets.items():
            (tmp_path / name).write_text(textwrap.dedent(content))
        return tmp_path

    return _make


class TestReady:
    def test_open_no_blockers_is_ready(self, ticket_dir):
        d = ticket_dir(
            **{
                "afg-test.ticket": """\
                    Id: afg
                    Title: Test
                    Author: a
                    Status: open
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """
            }
        )
        ready, warnings, total, open_count = find_ready(d)
        assert len(ready) == 1
        assert ready[0]["id"] == "afg"
        assert total == 1
        assert open_count == 1

    def test_open_blocked_by_closed_is_ready(self, ticket_dir):
        d = ticket_dir(
            **{
                "afg-test.ticket": """\
                    Id: afg
                    Title: Test
                    Author: a
                    Status: open
                    Created: 2026-01-01
                    Blocked-by: xyz

                    --- log ---
                    --- body ---
                """,
                "xyz-dep.ticket": """\
                    Id: xyz
                    Title: Dep
                    Author: a
                    Status: closed
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """,
            }
        )
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 1
        assert ready[0]["id"] == "afg"

    def test_open_blocked_by_open_is_not_ready(self, ticket_dir):
        d = ticket_dir(
            **{
                "afg-test.ticket": """\
                    Id: afg
                    Title: Test
                    Author: a
                    Status: open
                    Created: 2026-01-01
                    Blocked-by: xyz

                    --- log ---
                    --- body ---
                """,
                "xyz-dep.ticket": """\
                    Id: xyz
                    Title: Dep
                    Author: a
                    Status: open
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """,
            }
        )
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 1  # only xyz is ready (no blockers)
        assert ready[0]["id"] == "xyz"

    def test_transitive_block(self, ticket_dir):
        """A blocked by B, B blocked by C (open) → A not ready, B not ready."""
        d = ticket_dir(
            **{
                "a-one.ticket": """\
                    Id: a
                    Title: A
                    Author: x
                    Status: open
                    Created: 2026-01-01
                    Blocked-by: b

                    --- log ---
                    --- body ---
                """,
                "b-two.ticket": """\
                    Id: b
                    Title: B
                    Author: x
                    Status: open
                    Created: 2026-01-01
                    Blocked-by: c

                    --- log ---
                    --- body ---
                """,
                "c-three.ticket": """\
                    Id: c
                    Title: C
                    Author: x
                    Status: open
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """,
            }
        )
        ready, _, _, _ = find_ready(d)
        ids = {r["id"] for r in ready}
        assert ids == {"c"}  # only c is ready

    def test_closed_tickets_excluded(self, ticket_dir):
        d = ticket_dir(
            **{
                "afg-test.ticket": """\
                    Id: afg
                    Title: Test
                    Author: a
                    Status: closed
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """
            }
        )
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 0

    def test_missing_ref_warns(self, ticket_dir):
        d = ticket_dir(
            **{
                "afg-test.ticket": """\
                    Id: afg
                    Title: Test
                    Author: a
                    Status: open
                    Created: 2026-01-01
                    Blocked-by: gone

                    --- log ---
                    --- body ---
                """
            }
        )
        ready, warnings, _, _ = find_ready(d)
        assert len(ready) == 1  # treated as satisfied
        assert any("gone" in w for w in warnings)

    def test_all_closed_counts(self, ticket_dir):
        """When all tickets are closed, total > 0 and open_count == 0."""
        d = ticket_dir(
            **{
                "afg-test.ticket": """\
                    Id: afg
                    Title: Test
                    Author: a
                    Status: closed
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """,
                "xyz-dep.ticket": """\
                    Id: xyz
                    Title: Dep
                    Author: a
                    Status: closed
                    Created: 2026-01-01

                    --- log ---
                    --- body ---
                """,
            }
        )
        ready, _, total, open_count = find_ready(d)
        assert len(ready) == 0
        assert total == 2
        assert open_count == 0

    def test_empty_dir(self, ticket_dir):
        """Empty directory returns zero counts."""
        d = ticket_dir()  # no tickets
        ready, _, total, open_count = find_ready(d)
        assert len(ready) == 0
        assert total == 0
        assert open_count == 0

    def test_real_tickets(self):
        """Smoke test on real tickets — should not crash."""
        ticket_dir = Path(__file__).resolve().parent.parent / "tickets"
        if not ticket_dir.exists():
            pytest.skip("No tickets/")
        ready, warnings, total, open_count = find_ready(ticket_dir)
        assert isinstance(ready, list)
        assert total >= 0
        assert open_count >= 0


class TestWip:
    """Tests for .wip signal loading."""

    def test_load_wip_from_dir(self, tmp_path):
        wip_dir = tmp_path / "ticket-wip"
        wip_dir.mkdir()
        (wip_dir / "abc.wip").write_text("agent-1 2026-03-25T10:00Z")
        (wip_dir / "xyz.wip").write_text("agent-2 2026-03-25T11:00Z")
        result = _load_wip(wip_dir)
        assert result == {
            "abc": "agent-1 2026-03-25T10:00Z",
            "xyz": "agent-2 2026-03-25T11:00Z",
        }

    def test_load_wip_empty_dir(self, tmp_path):
        wip_dir = tmp_path / "ticket-wip"
        wip_dir.mkdir()
        assert _load_wip(wip_dir) == {}

    def test_load_wip_none(self):
        assert _load_wip(None) == {}

    def test_load_wip_missing_dir(self, tmp_path):
        assert _load_wip(tmp_path / "nonexistent") == {}
