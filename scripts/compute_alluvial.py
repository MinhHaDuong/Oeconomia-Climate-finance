"""Backward-compatibility shim for compute_alluvial.py.

DEPRECATED: This script has been split into focused, single-responsibility scripts.
Planned for removal in v1.0 milestone. Use the replacements directly:

  uv run python scripts/compute_breakpoints.py [--core-only] [--censor-gap N] [--robustness]
      Writes: tab_breakpoints.csv, tab_breakpoint_robustness.csv
              tab_k_sensitivity.csv (--robustness only)

  uv run python scripts/compute_clusters.py [--core-only]
      Writes: tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv

  uv run python scripts/compute_lexical.py
      Writes: tab_lexical_tfidf.csv

This wrapper runs all three in sequence, forwarding all arguments.
"""

import subprocess
import sys

extra = sys.argv[1:]

for script in [
    "scripts/compute_breakpoints.py",
    "scripts/compute_clusters.py",
    "scripts/compute_lexical.py",
]:
    result = subprocess.run([sys.executable, script] + extra)
    if result.returncode != 0:
        sys.exit(result.returncode)
