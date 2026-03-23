"""Test that #261 rename is complete: filter_flags importable, corpus_filter.py exists."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


def test_filter_flags_importable():
    """The filtering module is importable under its new name."""
    from filter_flags import flag_missing_metadata

    assert callable(flag_missing_metadata)


def test_corpus_filter_script_exists():
    """corpus_filter.py exists (renamed from corpus_refine.py)."""
    assert os.path.isfile(os.path.join(SCRIPTS_DIR, "corpus_filter.py"))


def test_old_names_removed():
    """Old refine_flags.py and corpus_refine.py no longer exist."""
    assert not os.path.isfile(os.path.join(SCRIPTS_DIR, "refine_flags.py"))
    assert not os.path.isfile(os.path.join(SCRIPTS_DIR, "corpus_refine.py"))
