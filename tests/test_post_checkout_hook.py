"""Tests for worktree setup: post-checkout hook and .worktreeinclude.

.worktreeinclude auto-copies .env and .dvc/config.local into worktrees
created by EnterWorktree. The post-checkout hook handles DVC data only.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "post-checkout"
WORKTREEINCLUDE = REPO / ".worktreeinclude"


def test_worktreeinclude_copies_env():
    """.worktreeinclude must list .env for auto-copy into worktrees."""
    contents = WORKTREEINCLUDE.read_text()
    assert ".env" in contents


def test_worktreeinclude_copies_dvc_config():
    """.worktreeinclude must list .dvc/config.local for auto-copy."""
    contents = WORKTREEINCLUDE.read_text()
    assert ".dvc/config.local" in contents


def test_hook_runs_dvc_checkout():
    """post-checkout hook must run dvc checkout for data population."""
    source = HOOK.read_text()
    assert "dvc checkout" in source


def test_hook_is_executable():
    """post-checkout must be executable."""
    assert HOOK.stat().st_mode & 0o111, "post-checkout hook is not executable"
