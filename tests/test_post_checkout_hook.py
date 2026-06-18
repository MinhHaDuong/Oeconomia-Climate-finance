"""Tests for worktree setup: post-checkout hook and .worktreeinclude.

.worktreeinclude auto-copies .env and .dvc/config.local into worktrees
created by EnterWorktree. The post-checkout hook only co-locates the uv
environment; DVC data is populated on demand via `make data`, never
eagerly at checkout time.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "post-checkout"
WORKTREEINCLUDE = REPO / ".worktreeinclude"
MAKEFILE = REPO / "Makefile"


def test_worktreeinclude_copies_env():
    """.worktreeinclude must list .env for auto-copy into worktrees."""
    contents = WORKTREEINCLUDE.read_text()
    assert ".env" in contents


def test_worktreeinclude_copies_dvc_config():
    """.worktreeinclude must list .dvc/config.local for auto-copy."""
    contents = WORKTREEINCLUDE.read_text()
    assert ".dvc/config.local" in contents


def test_hook_does_not_eagerly_checkout_data():
    """The hook must NOT run dvc checkout: that copied ~1.7 GB of DVC data into
    every worktree, timing out creation. Data population moved to `make data`."""
    source = HOOK.read_text()
    assert "dvc checkout" not in source


def test_makefile_data_target_checks_out_dvc():
    """Data is populated on demand: `make data` runs dvc checkout from the local
    cache (no network), so a worktree fetches data only when it actually needs it."""
    source = MAKEFILE.read_text()
    assert "\ndata:" in source
    # the data target's recipe runs dvc checkout
    recipe = source.split("\ndata:", 1)[1].split("\n\n", 1)[0]
    assert "dvc checkout" in recipe


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


def test_hook_replaces_stale_venv_symlink():
    """A dangling .venv symlink (target deleted) must not wedge the hook: use
    ln -sfn so the link is replaced idempotently rather than erroring on a
    pre-existing symlink, and only when .venv is absent or itself a symlink."""
    source = HOOK.read_text()
    assert "ln -sfn" in source
    assert "[ -L .venv ]" in source


def test_hook_serializes_concurrent_env_creation():
    """Concurrent worktree checkouts (parallel raids) must not race to build the
    shared env; the first-ever creation is serialized with flock."""
    source = HOOK.read_text()
    assert "flock" in source
