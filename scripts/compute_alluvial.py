"""Backward-compatibility shim for compute_alluvial.py.

DEPRECATED: This script has been split into focused, single-responsibility scripts.
Planned for removal in v1.0 milestone. Use the replacements directly:

  uv run python scripts/compute_breakpoints.py [--core-only] [--censor-gap N] [--robustness]
      Writes: tab_breakpoints.csv, tab_breakpoint_robustness.csv
              tab_k_sensitivity.csv (--robustness only)

  uv run python scripts/compute_clusters.py [--core-only] [--breaks Y1,Y2]
      Writes: tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv

  uv run python scripts/compute_lexical.py
      Writes: tab_lexical_tfidf.csv

This wrapper parses all flags itself (strict), then forwards only the flags
each sub-script accepts.
"""

import argparse
import subprocess
import sys

# Which flags each sub-script accepts
SCRIPT_FLAGS = {
    "scripts/compute_breakpoints.py": {"--core-only", "--censor-gap", "--robustness", "--no-pdf"},
    "scripts/compute_clusters.py":    {"--core-only", "--no-pdf", "--breaks"},
    "scripts/compute_lexical.py":     {"--no-pdf"},
}

parser = argparse.ArgumentParser(description="Backward-compat shim (deprecated)")
parser.add_argument("--core-only", action="store_true")
parser.add_argument("--censor-gap", type=int, default=0)
parser.add_argument("--robustness", action="store_true")
parser.add_argument("--no-pdf", action="store_true")
parser.add_argument("--breaks", type=str, default=None)
args = parser.parse_args()


def _build_argv(script):
    """Build argv list for a script, including only its accepted flags."""
    accepted = SCRIPT_FLAGS[script]
    argv = []
    if args.core_only and "--core-only" in accepted:
        argv.append("--core-only")
    if args.censor_gap and "--censor-gap" in accepted:
        argv.extend(["--censor-gap", str(args.censor_gap)])
    if args.robustness and "--robustness" in accepted:
        argv.append("--robustness")
    if args.no_pdf and "--no-pdf" in accepted:
        argv.append("--no-pdf")
    if args.breaks and "--breaks" in accepted:
        argv.extend(["--breaks", args.breaks])
    return argv


for script in SCRIPT_FLAGS:
    result = subprocess.run([sys.executable, script] + _build_argv(script))
    if result.returncode != 0:
        sys.exit(result.returncode)
