"""Guard the shared-env console-script shebangs against worktree-local drift.

The project uses one shared uv env at ``/data/envs/venv/oeconomia`` (torch
hardlink constraint, tickets 0145/0157); every worktree's ``.venv`` is a symlink
to it. When ``uv sync`` runs from a worktree it stamps each generated console
script (``bin/pytest``, ``bin/dvc``, ...) with the *unresolved* symlink path
``<worktree>/.venv/bin/python3``. Once that worktree is removed the interpreter
dangles and the console script falls through to the system tool (ticket 0158,
PR #807).

This test reads each ``bin/`` console-script shebang and asserts the interpreter
lives under the canonical (symlink-resolved) env directory — never a removable
worktree path such as ``.claude/worktrees/...`` or ``.../jobs/...``. The check is
on the *literal* shebang string, not its realpath: a worktree-local shebang
resolves through the ``.venv`` symlink back to the canonical interpreter, so
only the literal path exposes the drift.
"""

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV = REPO_ROOT / ".venv"


def _read_shebang_interpreter(script: Path) -> str | None:
    """Return the interpreter path from a python console-script shebang, or None.

    None when the file is not a python console script (binary, non-shebang, or a
    non-python shebang such as ``#!/bin/sh`` for ``activate``).
    """
    try:
        with open(script, "rb") as f:
            first = f.readline()
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    try:
        line = first.decode("utf-8").rstrip("\n")
    except UnicodeDecodeError:
        return None
    # Interpreter is the first whitespace-delimited token after "#!".
    interp = line[2:].strip().split()[0] if line[2:].strip() else ""
    if "python" not in os.path.basename(interp):
        return None
    return interp


def _console_scripts(bin_dir: Path) -> list[Path]:
    """Regular (non-symlink) files in ``bin/`` that carry a python shebang."""
    scripts = []
    for entry in sorted(bin_dir.iterdir()):
        if entry.is_symlink() or not entry.is_file():
            continue
        if _read_shebang_interpreter(entry) is not None:
            scripts.append(entry)
    return scripts


@pytest.mark.integration
def test_console_script_shebangs_are_canonical():
    """Every console-script shebang points at the canonical env interpreter.

    Fails if any shebang names a worktree-local interpreter (the ticket-0158
    regression) or a path that no longer exists.
    """
    if not VENV.exists():
        pytest.skip("no .venv (clean-room / CI without the shared env)")

    canonical = os.path.realpath(VENV)
    bin_dir = Path(canonical) / "bin"
    if not bin_dir.is_dir():
        pytest.skip(f"no bin/ under resolved env {canonical}")

    prefix = canonical + os.sep
    scripts = _console_scripts(bin_dir)
    assert scripts, f"no python console scripts found under {bin_dir}"

    offenders = []
    for script in scripts:
        interp = _read_shebang_interpreter(script)
        if interp is None:
            continue
        if not interp.startswith(prefix):
            offenders.append(f"{script.name}: shebang {interp} is outside {canonical}")
        elif not os.path.exists(interp):
            offenders.append(f"{script.name}: shebang interpreter {interp} does not exist")

    assert not offenders, (
        "console-script shebangs drifted off the canonical env "
        f"{canonical}:\n  " + "\n  ".join(offenders)
    )
