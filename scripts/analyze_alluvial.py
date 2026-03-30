"""Thin wrapper — runs the full alluvial pipeline in sequence.

DEPRECATED: Planned for removal in v1.0 milestone.
The pipeline has been split into focused, single-responsibility scripts.
Use them directly for better Makefile integration:

  uv run python scripts/compute_breakpoints.py [flags]  # tab_breakpoints.csv, tab_breakpoint_robustness.csv
  uv run python scripts/compute_clusters.py [flags]     # tab_alluvial.csv, cluster_labels.json
  uv run python scripts/compute_lexical.py [flags]      # tab_lexical_tfidf.csv
  uv run python scripts/plot_fig_breakpoints.py [flags] # fig_breakpoints.png
  uv run python scripts/plot_fig_alluvial.py [flags]    # fig_alluvial.png
  uv run python scripts/plot_alluvial_html.py [flags]  # fig_alluvial.html
  uv run python scripts/plot_fig_k_sensitivity.py       # fig_k_sensitivity.png (needs --robustness first)
  uv run python scripts/plot_fig_lexical_tfidf.py       # fig_lexical_tfidf_{year}.png

This wrapper exists so that old usage (e.g. `uv run python scripts/analyze_alluvial.py`)
continues to work without modification until v1.0.
"""

import argparse
import subprocess
import sys

# Which flags each sub-script accepts
SCRIPT_FLAGS = {
    "scripts/compute_breakpoints.py": {"--core-only", "--censor-gap", "--robustness"},
    "scripts/compute_clusters.py":    {"--core-only", "--breaks"},
    "scripts/compute_lexical.py":     set(),
    "scripts/plot_fig_breakpoints.py": {"--core-only", "--censor-gap", "--pdf"},
    "scripts/plot_fig_alluvial.py":    {"--core-only", "--censor-gap", "--pdf"},
    "scripts/plot_alluvial_html.py":   {"--core-only", "--censor-gap"},
}

parser = argparse.ArgumentParser(description="Full alluvial pipeline (deprecated)")
parser.add_argument("--core-only", action="store_true")
parser.add_argument("--censor-gap", type=int, default=0)
parser.add_argument("--robustness", action="store_true")
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
    if args.breaks and "--breaks" in accepted:
        argv.extend(["--breaks", args.breaks])
    return argv


for script in SCRIPT_FLAGS:
    result = subprocess.run([sys.executable, script] + _build_argv(script))
    if result.returncode != 0:
        sys.exit(result.returncode)
