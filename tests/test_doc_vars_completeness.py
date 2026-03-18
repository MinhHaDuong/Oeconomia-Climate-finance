"""Verify DOC_VARS in compute_vars.py lists every {{< meta >}} variable.

Scans each .qmd and its {{< include >}}'d files for {{< meta X >}} shortcodes,
then checks that every variable X appears in the DOC_VARS mapping for that
document. Prevents silent empty-string rendering when a new variable is
added to prose but not registered in compute_vars.py.
"""

import os
import re
import sys

import pytest

# Allow importing from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from compute_vars import DOC_VARS  # noqa: E402

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "content")

META_RE = re.compile(r"\{\{<\s*meta\s+(\w+)\s*>\}\}")
INCLUDE_RE = re.compile(r"\{\{<\s*include\s+(\S+)\s*>\}\}")


def _find_meta_vars(filepath):
    """Return set of variable names used in {{< meta X >}} shortcodes."""
    with open(filepath) as f:
        text = f.read()
    return set(META_RE.findall(text))


def _find_includes(filepath):
    """Return list of included file paths (relative to content dir)."""
    with open(filepath) as f:
        text = f.read()
    return INCLUDE_RE.findall(text)


def _all_vars_for_doc(qmd_path):
    """Collect all meta variables from a .qmd and its includes, recursively."""
    all_vars = _find_meta_vars(qmd_path)
    for inc in _find_includes(qmd_path):
        inc_path = os.path.join(os.path.dirname(qmd_path), inc)
        if os.path.isfile(inc_path):
            all_vars |= _find_meta_vars(inc_path)
            # One level of nested includes
            for nested in _find_includes(inc_path):
                nested_path = os.path.join(os.path.dirname(inc_path), nested)
                if os.path.isfile(nested_path):
                    all_vars |= _find_meta_vars(nested_path)
    return all_vars


@pytest.mark.parametrize("doc_name", list(DOC_VARS.keys()))
def test_doc_vars_complete(doc_name):
    """Every {{< meta X >}} in doc + includes must appear in DOC_VARS."""
    qmd_path = os.path.join(CONTENT_DIR, f"{doc_name}.qmd")
    if not os.path.isfile(qmd_path):
        pytest.skip(f"{qmd_path} not found")

    used = _all_vars_for_doc(qmd_path)
    declared = set(DOC_VARS[doc_name])
    missing = used - declared
    assert not missing, (
        f"{doc_name}: {len(missing)} variable(s) used in prose but not in DOC_VARS: "
        f"{sorted(missing)}"
    )


@pytest.mark.parametrize("doc_name", list(DOC_VARS.keys()))
def test_doc_vars_no_extras(doc_name):
    """DOC_VARS should not list variables that no shortcode uses (dead entries)."""
    qmd_path = os.path.join(CONTENT_DIR, f"{doc_name}.qmd")
    if not os.path.isfile(qmd_path):
        pytest.skip(f"{qmd_path} not found")

    used = _all_vars_for_doc(qmd_path)
    declared = set(DOC_VARS[doc_name])
    extra = declared - used
    assert not extra, (
        f"{doc_name}: {len(extra)} variable(s) in DOC_VARS but unused in prose: "
        f"{sorted(extra)}"
    )
