"""Ticket 0160: submission-workflow docs must use the papiers/<state>/<track>
convention, not the `release/` directory removed in the 0159 reorg.

The submission-branch mechanism is kept (it freezes the manuscript *source* and
its revision history); only the artifact-carrying role moved out of the repo to
untracked `papiers/<state>/<track>/`. Process docs that still send new submission
artifacts to `release/` are stale and would misdirect the next submission.

Dated historical snapshots (braindumps) intentionally describe the pre-0159
layout — the 0160 invariant says preserve historical events, rewrite only
forward-looking process docs — so they are allowlisted.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCOPE = [".agent", ".claude/skills", "docs"]
ALLOWLIST = {
    "docs/braindump-2026-03-18.md",
    "docs/braindump-2026-03-28.md",
}


def _scoped_md_files():
    for top in SCOPE:
        yield from (REPO / top).rglob("*.md")


def test_no_release_dir_refs_in_process_docs():
    offenders = []
    for path in _scoped_md_files():
        rel = path.relative_to(REPO).as_posix()
        if rel in ALLOWLIST:
            continue
        if "release/" in path.read_text(encoding="utf-8"):
            offenders.append(rel)
    assert not offenders, (
        "These docs still reference the removed release/ directory; route "
        "submission records to papiers/<state>/<track>/ and the release journal "
        "to docs/ (ticket 0160):\n  " + "\n  ".join(sorted(offenders))
    )
