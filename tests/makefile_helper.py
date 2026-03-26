"""Shared helper for tests that read the Makefile.

Resolves `include mk/*.mk` directives so tests see the effective Makefile
content, regardless of how rules are split across modules.
"""

import os
import re

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
MAKEFILE = os.path.join(PROJECT_ROOT, "Makefile")


def read_makefile():
    """Read the Makefile and inline all `include` directives."""
    with open(MAKEFILE) as f:
        content = f.read()
    resolved = []
    for line in content.splitlines(keepends=True):
        m = re.match(r"^include\s+(.+)$", line)
        if m:
            include_path = os.path.join(PROJECT_ROOT, m.group(1).strip())
            if os.path.isfile(include_path):
                with open(include_path) as inc:
                    resolved.append(inc.read())
                continue
        resolved.append(line)
    return "".join(resolved)
