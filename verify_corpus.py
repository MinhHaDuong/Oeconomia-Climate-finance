#!/usr/bin/env python3
"""Level 2 verification: compare rebuilt corpus against shipped reference.

Checks structural equivalence rather than byte-identity, because API
responses evolve (new publications, updated citation counts).

Exit code 0 = pass, 1 = structural mismatch.
"""

import os
import sys

import numpy as np
import pandas as pd

REF_DIR = os.path.join("data", "catalogs-reference")
NEW_DIR = os.path.join("data", "catalogs")

TOLERANCE_PCT = 5  # row count tolerance


def compare_csv(name: str, key_col: str = "id") -> bool:
    """Compare a CSV file between reference and rebuilt."""
    ref_path = os.path.join(REF_DIR, name)
    new_path = os.path.join(NEW_DIR, name)

    if not os.path.isfile(ref_path):
        print(f"  SKIP {name}: no reference file")
        return True
    if not os.path.isfile(new_path):
        print(f"  FAIL {name}: rebuilt file missing")
        return False

    ref = pd.read_csv(ref_path, low_memory=False)
    new = pd.read_csv(new_path, low_memory=False)

    ok = True

    # Schema check
    ref_cols = set(ref.columns)
    new_cols = set(new.columns)
    if ref_cols != new_cols:
        missing = ref_cols - new_cols
        extra = new_cols - ref_cols
        if missing:
            print(f"  WARN {name}: missing columns: {missing}")
        if extra:
            print(f"  INFO {name}: new columns: {extra}")

    # Row count tolerance
    ref_n, new_n = len(ref), len(new)
    pct_diff = abs(new_n - ref_n) / max(ref_n, 1) * 100
    if pct_diff > TOLERANCE_PCT:
        print(f"  FAIL {name}: row count {new_n} vs reference {ref_n} "
              f"({pct_diff:.1f}% difference, tolerance {TOLERANCE_PCT}%)")
        ok = False
    else:
        print(f"  OK   {name}: {new_n} rows (reference {ref_n}, "
              f"{pct_diff:.1f}% difference)")

    return ok


def compare_embeddings() -> bool:
    """Compare embeddings archive dimensions."""
    ref_path = os.path.join(REF_DIR, "refined_embeddings.npz")
    new_path = os.path.join(NEW_DIR, "refined_embeddings.npz")

    if not os.path.isfile(ref_path):
        print("  SKIP embeddings: no reference file")
        return True
    if not os.path.isfile(new_path):
        print("  FAIL embeddings: rebuilt file missing")
        return False

    ref = np.load(ref_path)
    new = np.load(new_path)

    ref_shape = ref["vectors"].shape
    new_shape = new["vectors"].shape

    if ref_shape[1] != new_shape[1]:
        print(f"  FAIL embeddings: dimension mismatch "
              f"{new_shape[1]} vs reference {ref_shape[1]}")
        return False

    pct_diff = abs(new_shape[0] - ref_shape[0]) / max(ref_shape[0], 1) * 100
    if pct_diff > TOLERANCE_PCT:
        print(f"  FAIL embeddings: {new_shape[0]} vectors vs reference "
              f"{ref_shape[0]} ({pct_diff:.1f}% difference)")
        return False

    print(f"  OK   embeddings: {new_shape} (reference {ref_shape})")
    return True


def main() -> int:
    print("=" * 60)
    print("Level 2 verification: structural comparison")
    print("=" * 60)

    if not os.path.isdir(REF_DIR):
        print(f"\nReference directory {REF_DIR} not found.")
        print("To set up: cp -r data/catalogs data/catalogs-reference")
        print("           (before rebuilding)")
        return 1

    results = []
    results.append(compare_csv("refined_works.csv"))
    results.append(compare_csv("corpus_audit.csv"))
    results.append(compare_csv("citations.csv", key_col="source_doi"))
    results.append(compare_embeddings())

    print()
    if all(results):
        print("VERIFY: PASS — rebuilt corpus is structurally equivalent")
        return 0
    else:
        print("VERIFY: FAIL — structural differences found (see above)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
