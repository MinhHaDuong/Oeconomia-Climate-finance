"""Cross-implementation smoke tests for ticket tools.

Runs the Python and bash-fast implementations on real tickets and
verifies they produce identical output (text mode).  Go is tested
only when the binary exists (requires manual `go build`).
"""

import subprocess
import shutil
from pathlib import Path

import pytest

TICKET_DIR = Path(__file__).resolve().parent.parent / "tickets"
TOOLS_DIR = TICKET_DIR / "tools"
BASH_DIR = TOOLS_DIR / "bash-fast"
GO_DIR = TOOLS_DIR / "go"
GO_BIN = GO_DIR / "ticket-tools"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, **kwargs
    )


def _py(script: str, *args: str) -> str:
    r = _run(["python3", str(TOOLS_DIR / script), *args])
    assert r.returncode == 0, f"Python {script} failed:\n{r.stderr}"
    return r.stdout


def _sh(script: str, *args: str) -> str:
    r = _run(["sh", str(BASH_DIR / script), *args])
    assert r.returncode == 0, f"Bash {script} failed:\n{r.stderr}"
    return r.stdout


def _go(subcmd: str, *args: str) -> str:
    r = _run([str(GO_BIN), subcmd, *args])
    assert r.returncode == 0, f"Go {subcmd} failed:\n{r.stderr}"
    return r.stdout


@pytest.fixture(autouse=True)
def _require_tickets():
    if not TICKET_DIR.exists() or not list(TICKET_DIR.glob("*.ticket")):
        pytest.skip("No tickets/ directory or no .ticket files")


# --- Helpers to normalize output for comparison ---

def _normalize(text: str) -> str:
    """Strip trailing whitespace from each line, drop empty trailing lines."""
    lines = [l.rstrip() for l in text.strip().splitlines()]
    return "\n".join(lines)


# --- Tests ---

class TestValidateCrossImpl:
    """validate_tickets: Python vs bash-fast (vs Go if available)."""

    def test_python_passes(self):
        out = _py("validate_tickets.py", str(TICKET_DIR))
        assert "PASS" in out

    @pytest.mark.skipif(
        not shutil.which("awk"), reason="awk not available"
    )
    def test_bash_matches_python(self):
        py_out = _normalize(_py("validate_tickets.py", str(TICKET_DIR)))
        sh_out = _normalize(_sh("validate_tickets.sh", str(TICKET_DIR)))
        assert py_out == sh_out

    @pytest.mark.skipif(not GO_BIN.exists(), reason="Go binary not built")
    def test_go_matches_python(self):
        py_out = _normalize(_py("validate_tickets.py", str(TICKET_DIR)))
        go_out = _normalize(_go("validate", str(TICKET_DIR)))
        assert py_out == go_out


class TestReadyCrossImpl:
    """ready_tickets: Python vs bash-fast (vs Go if available)."""

    def test_python_runs(self):
        out = _py("ready_tickets.py", str(TICKET_DIR))
        assert isinstance(out, str)

    @pytest.mark.skipif(
        not shutil.which("awk"), reason="awk not available"
    )
    def test_bash_matches_python(self):
        py_out = _normalize(_py("ready_tickets.py", str(TICKET_DIR)))
        sh_out = _normalize(_sh("ready_tickets.sh", str(TICKET_DIR)))
        assert py_out == sh_out

    @pytest.mark.skipif(not GO_BIN.exists(), reason="Go binary not built")
    def test_go_matches_python(self):
        py_out = _normalize(_py("ready_tickets.py", str(TICKET_DIR)))
        go_out = _normalize(_go("ready", str(TICKET_DIR)))
        assert py_out == go_out


class TestArchiveCrossImpl:
    """archive_tickets (dry-run): Python vs bash-fast (vs Go if available)."""

    def test_python_runs(self):
        out = _py("archive_tickets.py", str(TICKET_DIR), "--days=1")
        assert isinstance(out, str)

    @pytest.mark.skipif(
        not shutil.which("awk"), reason="awk not available"
    )
    def test_bash_matches_python(self):
        py_out = _normalize(
            _py("archive_tickets.py", str(TICKET_DIR), "--days=1")
        )
        sh_out = _normalize(
            _sh("archive_tickets.sh", str(TICKET_DIR), "--days=1")
        )
        assert py_out == sh_out

    @pytest.mark.skipif(not GO_BIN.exists(), reason="Go binary not built")
    def test_go_matches_python(self):
        py_out = _normalize(
            _py("archive_tickets.py", str(TICKET_DIR), "--days=1")
        )
        go_out = _normalize(
            _go("archive", str(TICKET_DIR), "--days=1")
        )
        assert py_out == go_out
