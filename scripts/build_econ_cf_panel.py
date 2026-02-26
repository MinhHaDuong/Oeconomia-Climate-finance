#!/usr/bin/env python3
"""Build harmonized yearly panel for economics and climate-finance counts.

Orchestrates:
1) count_openalex_econ_cf.py --scope economics
2) count_openalex_econ_cf.py --scope finance
3) count_openalex_econ_fin_overlap.py
4) count_repec_econ_cf.py (if RePEc mirror exists)

Then merges OpenAlex + RePEc into one panel CSV.

Outputs:
- $DATA/catalogs/openalex_econ_yearly.csv
- $DATA/catalogs/openalex_finance_yearly.csv
- $DATA/catalogs/openalex_econ_fin_overlap.csv
- $DATA/catalogs/repec_econ_yearly.csv
- $DATA/catalogs/econ_cf_yearly_panel.csv

Usage:
    uv run python scripts/build_econ_cf_panel.py
"""

import argparse
import os
import subprocess
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, save_csv

SCRIPTS_DIR = os.path.dirname(__file__)
DEFAULT_REPEC_ROOT = os.path.expanduser(
    os.environ.get("REPEC_ROOT", "~/data/datasets/external/RePEc")
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build OpenAlex+RePEc economics/climate-finance panel")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="OpenAlex API delay in seconds")
    parser.add_argument("--repec-root", type=str, default=DEFAULT_REPEC_ROOT,
                        help="Path to local RePEc ReDIF root")
    parser.add_argument("--skip-repec", action="store_true",
                        help="Skip RePEc counting (e.g. if mirror unavailable)")
    parser.add_argument("--panel-out", type=str,
                        default=os.path.join(CATALOGS_DIR, "econ_cf_yearly_panel.csv"),
                        help="Output merged panel CSV")
    return parser.parse_args()


def run_script(script_name, extra_args=None):
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script_name)]
    if extra_args:
        cmd.extend(extra_args)
    print(f"  Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)


def main():
    args = parse_args()
    delay = str(args.delay)

    print("[1/4] OpenAlex economics yearly counts")
    run_script("count_openalex_econ_cf.py", ["--scope", "economics", "--delay", delay])

    print("[2/4] OpenAlex finance yearly counts")
    run_script("count_openalex_econ_cf.py", ["--scope", "finance", "--delay", delay])

    print("[3/4] Econ/Finance overlap (ID-level sets)")
    run_script("count_openalex_econ_fin_overlap.py", ["--delay", delay])

    if args.skip_repec:
        print("[4/4] Skipping RePEc (--skip-repec)")
    elif not os.path.isdir(args.repec_root):
        print(f"[4/4] Skipping RePEc (mirror not found at {args.repec_root})")
    else:
        print("[4/4] RePEc yearly counts")
        run_script("count_repec_econ_cf.py", ["--repec-root", args.repec_root])

    # Merge into panel
    p_econ = os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv")
    p_repec = os.path.join(CATALOGS_DIR, "repec_econ_yearly.csv")

    frames = []
    if os.path.exists(p_econ):
        frames.append(pd.read_csv(p_econ))
    if os.path.exists(p_repec):
        frames.append(pd.read_csv(p_repec))

    if frames:
        panel = pd.concat(frames, ignore_index=True).sort_values(
            ["source", "year"]).reset_index(drop=True)
        save_csv(panel, args.panel_out)
        print(f"Panel: {len(panel)} rows, sources: {sorted(panel['source'].unique())}")
    else:
        print("No data to merge.")

    print("Done.")


if __name__ == "__main__":
    main()
