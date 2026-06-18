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


def test_hook_points_venv_at_shared_env_on_data():
    """The hook must symlink .venv to a shared env that lives beside the uv
    cache on /data, so uv hardlinks wheels instead of copying ~1.8 GB per
    worktree (a cross-filesystem copy that makes worktree creation time out)."""
    source = HOOK.read_text()
    assert "/data/envs" in source
    assert "ln -s" in source and ".venv" in source


def test_hook_precreates_shared_env_before_symlinking():
    """A dangling .venv symlink makes `uv run` error, so the shared env must be
    created (uv venv) before the symlink is made."""
    source = HOOK.read_text()
    assert "uv venv" in source
    # uv venv must appear before the symlink in the source order.
    assert source.index("uv venv") < source.index("ln -s")


def test_hook_skips_shared_env_without_data_filesystem():
    """The shared-env step must be guarded so the default local .venv is used
    where /data is absent (portability to machines without the data disk)."""
    source = HOOK.read_text()
    assert "[ -d /data/envs ]" in source
