"""Tests for ready_tickets.py — find unblocked open tickets."""

import textwrap
from pathlib import Path

import pytest

from ready_tickets import find_ready


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
        ready, warnings = find_ready(d)
        assert len(ready) == 1
        assert ready[0]["id"] == "afg"

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
        ready, _ = find_ready(d)
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
        ready, _ = find_ready(d)
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
        ready, _ = find_ready(d)
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
        ready, _ = find_ready(d)
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
        ready, warnings = find_ready(d)
        assert len(ready) == 1  # treated as satisfied
        assert any("gone" in w for w in warnings)

    def test_real_tickets(self):
        """Smoke test on real tickets — should not crash."""
        ticket_dir = Path(__file__).resolve().parent.parent / "tickets"
        if not ticket_dir.exists():
            pytest.skip("No tickets/")
        ready, warnings = find_ready(ticket_dir)
        # Just verify it runs without error
        assert isinstance(ready, list)
