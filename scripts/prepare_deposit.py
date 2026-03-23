"""Prepare data files for the Zenodo deposit.

Reads unified_works.csv and writes climate_finance_corpus.csv with:
- Abstract column dropped (publisher redistribution restrictions)
- Column from_scispsace renamed to from_scispace if present

Usage:
    uv run python scripts/prepare_deposit.py [--out-dir DIR]
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, get_logger

log = get_logger("prepare_deposit")

DEPOSIT_COLUMNS_TO_DROP = ["abstract"]
DEPOSIT_RENAMES = {"from_scispsace": "from_scispace"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=os.path.join(CATALOGS_DIR, "deposit"),
        help="Output directory for deposit files",
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # --- climate_finance_corpus.csv ---
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    log.info("Reading %s", unified_path)
    df = pd.read_csv(unified_path)
    n_raw = len(df)

    # Drop abstract
    dropped = [c for c in DEPOSIT_COLUMNS_TO_DROP if c in df.columns]
    if dropped:
        df = df.drop(columns=dropped)
        log.info("Dropped columns: %s", dropped)

    # Rename legacy typo column
    renames = {k: v for k, v in DEPOSIT_RENAMES.items() if k in df.columns}
    if renames:
        df = df.rename(columns=renames)
        log.info("Renamed columns: %s", renames)

    out_path = os.path.join(args.out_dir, "climate_finance_corpus.csv")
    df.to_csv(out_path, index=False)
    log.info("Wrote %s (%d rows, %d columns)", out_path, n_raw, len(df.columns))

    # --- Verify ---
    if "abstract" in df.columns:
        log.error("abstract column still present!")
        sys.exit(1)
    if "from_scispsace" in df.columns:
        log.error("from_scispsace typo still present!")
        sys.exit(1)

    log.info("Deposit files ready in %s", args.out_dir)


if __name__ == "__main__":
    main()
