"""Thin wrapper — runs the full alluvial pipeline in sequence.

DEPRECATED: Planned for removal in v1.0 milestone.
The pipeline has been split into focused, single-responsibility scripts.
Use them directly for better Makefile integration:

  uv run python scripts/compute_breakpoints.py [flags]  # tab_breakpoints.csv, tab_breakpoint_robustness.csv
  uv run python scripts/compute_clusters.py [flags]     # tab_alluvial.csv, cluster_labels.json
  uv run python scripts/compute_lexical.py [flags]      # tab_lexical_tfidf.csv
  uv run python scripts/plot_fig_breakpoints.py [flags] # fig_breakpoints.png
  uv run python scripts/plot_fig_alluvial.py [flags]    # fig_alluvial.png + .html
  uv run python scripts/plot_fig_k_sensitivity.py       # fig_k_sensitivity.png (needs --robustness first)
  uv run python scripts/plot_fig_lexical_tfidf.py       # fig_lexical_tfidf_{year}.png

This wrapper exists so that old usage (e.g. `uv run python scripts/analyze_alluvial.py`)
continues to work without modification until v1.0.
"""

import subprocess
import sys

extra = sys.argv[1:]

for script in [
    "scripts/compute_breakpoints.py",
    "scripts/compute_clusters.py",
    "scripts/compute_lexical.py",
    "scripts/plot_fig_breakpoints.py",
    "scripts/plot_fig_alluvial.py",
]:
    cmd = [sys.executable, script] + extra
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
