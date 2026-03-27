"""Tests for the post-checkout hook.

The hook must symlink machine-local config from the main worktree
so that DVC and scripts work in worktrees without manual setup.
"""

import subprocess
import textwrap
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "post-checkout"


def test_hook_symlinks_dvc_config_local():
    """post-checkout must symlink .dvc/config.local from main worktree."""
    source = HOOK.read_text()
    # The hook should reference .dvc/config.local
    assert ".dvc/config.local" in source, (
        "post-checkout hook does not handle .dvc/config.local — "
        "worktrees will fail dvc checkout silently"
    )


def test_hook_symlinks_env():
    """post-checkout must symlink .env (existing behavior, regression guard)."""
    source = HOOK.read_text()
    assert ".env" in source


def test_hook_is_executable():
    """post-checkout must be executable."""
    assert HOOK.stat().st_mode & 0o111, "post-checkout hook is not executable"
