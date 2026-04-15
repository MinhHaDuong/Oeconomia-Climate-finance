"""Convergence analysis across multi-channel change point detections.

Reads the breaks table from compute_changepoints.py and counts how many
(method × detector × params) combinations detect a break at each year,
with ±1 year tolerance.

Reads:  tab_changepoints.csv
Writes: tab_convergence.csv

Usage:
    python3 scripts/compute_convergence.py \
        --output content/tables/tab_convergence.csv \
        --input content/tables/tab_changepoints.csv
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compute_changepoints import compute_convergence
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_convergence")


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    if not io_args.input:
        # Default: look for changepoints table
        tables_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "content", "tables",
        )
        input_path = os.path.join(tables_dir, "tab_changepoints.csv")
    else:
        input_path = io_args.input[0]

    breaks_df = pd.read_csv(input_path)
    log.info("Loaded %d break rows from %s", len(breaks_df), input_path)

    convergence_df = compute_convergence(breaks_df)

    convergence_df.to_csv(io_args.output, index=False)
    log.info("Saved convergence table -> %s (%d rows)", io_args.output,
             len(convergence_df))

    if not convergence_df.empty:
        top = convergence_df.nlargest(5, "pct_total")
        log.info("Top convergence years:")
        for _, row in top.iterrows():
            log.info("  %d: %.1f%% (%d detections, methods: %s)",
                     row["year"], row["pct_total"] * 100,
                     row["n_total"], row["methods_detecting"])

    log.info("Done.")


if __name__ == "__main__":
    main()
