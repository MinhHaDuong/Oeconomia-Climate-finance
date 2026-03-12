"""Thin wrapper — calls compute_alluvial.py then both plot scripts in sequence.

DEPRECATED since #46 (March 2026).  Scheduled for removal after v1.0 release.
Use the individual scripts directly for better Makefile integration:
  uv run python scripts/compute_alluvial.py [flags]     # writes CSVs + JSON
  uv run python scripts/plot_fig_breakpoints.py [flags]  # writes fig_breakpoints.png
  uv run python scripts/plot_fig_alluvial.py [flags]     # writes fig_alluvial.png + .html

This wrapper exists so that old usage (e.g. `uv run python scripts/analyze_alluvial.py`)
continues to work without modification.  It will be removed in the next major release;
migrate callers to the individual scripts above.
"""

import subprocess
import sys
import warnings

warnings.warn(
    "analyze_alluvial.py is deprecated since #46 and will be removed after v1.0. "
    "Use compute_alluvial.py + plot_fig_breakpoints.py + plot_fig_alluvial.py directly.",
    DeprecationWarning,
    stacklevel=1,
)

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
