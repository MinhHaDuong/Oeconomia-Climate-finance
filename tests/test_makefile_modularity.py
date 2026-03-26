"""Tests for Makefile modularity — #405.

Verify that shared Makefile logic is extracted into mk/*.mk include files
and the top-level Makefile uses `include` directives to pull them in.
"""

import glob
import os
import re

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
MK_DIR = os.path.join(PROJECT_ROOT, "mk")
MAKEFILE = os.path.join(PROJECT_ROOT, "Makefile")


class TestMkModulesExist:
    """mk/ directory contains at least one .mk include file."""

    def test_mk_directory_exists(self):
        assert os.path.isdir(MK_DIR), "mk/ directory does not exist"

    def test_at_least_one_mk_file(self):
        mk_files = glob.glob(os.path.join(MK_DIR, "*.mk"))
        assert len(mk_files) >= 1, "mk/ must contain at least one .mk file"


class TestMakefileUsesIncludes:
    """Top-level Makefile must include mk/*.mk modules."""

    def test_makefile_has_include_directive(self):
        with open(MAKEFILE) as f:
            content = f.read()
        assert re.search(r"^include\s+mk/", content, re.MULTILINE), \
            "Makefile must use 'include mk/' directives"
