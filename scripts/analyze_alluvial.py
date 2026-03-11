"""Thin wrapper — calls compute_alluvial.py then both plot scripts in sequence.

DEPRECATED: Use the individual scripts directly for better Makefile integration:
  uv run python scripts/compute_alluvial.py [flags]     # writes CSVs + JSON
  uv run python scripts/plot_fig_breakpoints.py [flags] # writes fig_breakpoints.png
  uv run python scripts/plot_fig_alluvial.py [flags]    # writes fig_alluvial.png + .html

This wrapper exists so that old usage (e.g. `uv run python scripts/analyze_alluvial.py`)
continues to work without modification.
"""

import subprocess
import sys

# Forward all arguments to each sub-script
extra = sys.argv[1:]

for script in [
    "scripts/compute_alluvial.py",
    "scripts/plot_fig_breakpoints.py",
    "scripts/plot_fig_alluvial.py",
]:
    cmd = [sys.executable, script] + extra
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)
