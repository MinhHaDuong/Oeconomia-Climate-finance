"""Tests for ready_tickets.py — find unblocked open %ticket v1 files."""

import textwrap
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tickets" / "tools"))

from ready_tickets import find_ready, _load_wip


@pytest.fixture
def ticket_dir(tmp_path):
    def _make(**tickets):
        for name, content in tickets.items():
            (tmp_path / name).write_text(textwrap.dedent(content))
        return tmp_path
    return _make


class TestReady:
    def test_open_no_blockers_is_ready(self, ticket_dir):
        d = ticket_dir(**{"0001-test.ticket": """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01

            --- log ---
            --- body ---
        """})
        ready, warnings, total, open_count = find_ready(d)
        assert len(ready) == 1
        assert ready[0]["id"] == "0001"
        assert total == 1
        assert open_count == 1

    def test_open_blocked_by_closed_is_ready(self, ticket_dir):
        d = ticket_dir(**{
            "0001-test.ticket": """\
                %ticket v1
                Title: Test
                Author: a
                Status: open
                Created: 2026-01-01
                Blocked-by: 0002

                --- log ---
                --- body ---
            """,
            "0002-dep.ticket": """\
                %ticket v1
                Title: Dep
                Author: a
                Status: closed
                Created: 2026-01-01

                --- log ---
                --- body ---
            """,
        })
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 1
        assert ready[0]["id"] == "0001"

    def test_open_blocked_by_open_is_not_ready(self, ticket_dir):
        d = ticket_dir(**{
            "0001-test.ticket": """\
                %ticket v1
                Title: Test
                Author: a
                Status: open
                Created: 2026-01-01
                Blocked-by: 0002

                --- log ---
                --- body ---
            """,
            "0002-dep.ticket": """\
                %ticket v1
                Title: Dep
                Author: a
                Status: open
                Created: 2026-01-01

                --- log ---
                --- body ---
            """,
        })
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 1  # only 0002 is ready
        assert ready[0]["id"] == "0002"

    def test_transitive_block(self, ticket_dir):
        d = ticket_dir(**{
            "0001-a.ticket": """\
                %ticket v1
                Title: A
                Author: x
                Status: open
                Created: 2026-01-01
                Blocked-by: 0002

                --- log ---
                --- body ---
            """,
            "0002-b.ticket": """\
                %ticket v1
                Title: B
                Author: x
                Status: open
                Created: 2026-01-01
                Blocked-by: 0003

                --- log ---
                --- body ---
            """,
            "0003-c.ticket": """\
                %ticket v1
                Title: C
                Author: x
                Status: open
                Created: 2026-01-01

                --- log ---
                --- body ---
            """,
        })
        ready, _, _, _ = find_ready(d)
        ids = {r["id"] for r in ready}
        assert ids == {"0003"}

    def test_closed_tickets_excluded(self, ticket_dir):
        d = ticket_dir(**{"0001-test.ticket": """\
            %ticket v1
            Title: Test
            Author: a
            Status: closed
            Created: 2026-01-01

            --- log ---
            --- body ---
        """})
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 0

    def test_pending_tickets_excluded(self, ticket_dir):
        d = ticket_dir(**{"0001-test.ticket": """\
            %ticket v1
            Title: Test
            Author: a
            Status: pending
            Created: 2026-01-01

            --- log ---
            --- body ---
        """})
        ready, _, _, open_count = find_ready(d)
        assert len(ready) == 0
        assert open_count == 0  # pending is not open

    def test_github_ref_treated_as_satisfied(self, ticket_dir):
        d = ticket_dir(**{"0001-test.ticket": """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: gh#435

            --- log ---
            --- body ---
        """})
        ready, _, _, _ = find_ready(d)
        assert len(ready) == 1

    def test_missing_ref_warns(self, ticket_dir):
        d = ticket_dir(**{"0001-test.ticket": """\
            %ticket v1
            Title: Test
            Author: a
            Status: open
            Created: 2026-01-01
            Blocked-by: 9999

            --- log ---
            --- body ---
        """})
        ready, warnings, _, _ = find_ready(d)
        assert len(ready) == 1
        assert any("9999" in w for w in warnings)

    def test_empty_dir(self, ticket_dir):
        d = ticket_dir()
        ready, _, total, open_count = find_ready(d)
        assert len(ready) == 0
        assert total == 0
        assert open_count == 0

    def test_real_tickets(self):
        ticket_dir = Path(__file__).resolve().parent.parent / "tickets"
        if not ticket_dir.exists():
            pytest.skip("No tickets/")
        ready, warnings, total, open_count = find_ready(ticket_dir)
        assert isinstance(ready, list)
        assert total >= 0


class TestWip:
    def test_load_wip_from_dir(self, tmp_path):
        wip_dir = tmp_path / "ticket-wip"
        wip_dir.mkdir()
        (wip_dir / "0001.wip").write_text("agent-1 2026-03-25T10:00Z")
        (wip_dir / "0002.wip").write_text("agent-2 2026-03-25T11:00Z")
        result = _load_wip(wip_dir)
        assert result == {
            "0001": "agent-1 2026-03-25T10:00Z",
            "0002": "agent-2 2026-03-25T11:00Z",
        }

    def test_load_wip_empty_dir(self, tmp_path):
        wip_dir = tmp_path / "ticket-wip"
        wip_dir.mkdir()
        assert _load_wip(wip_dir) == {}

    def test_load_wip_none(self):
        assert _load_wip(None) == {}
