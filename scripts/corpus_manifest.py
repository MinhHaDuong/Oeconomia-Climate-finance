#!/usr/bin/env python3
"""Generate a manifest of Phase 1 corpus outputs.

Records MD5 checksums and basic stats for each contract file so that
Phase 2 scripts can verify they are working with a known corpus snapshot.

Writes: $DATA/catalogs/corpus_manifest.json

Usage:
    uv run python scripts/corpus_manifest.py
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, PHASE1_OUTPUTS


def md5_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_stats(path: str) -> dict:
    """Return MD5 + format-specific stats for a corpus file."""
    info = {"md5": md5_file(path), "bytes": os.path.getsize(path)}
    if path.endswith(".csv"):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        info["rows"] = len(df)
        info["columns"] = list(df.columns)
    elif path.endswith(".npz"):
        data = np.load(path)
        for key in data.files:
            info[f"array_{key}_shape"] = list(data[key].shape)
    return info


def main():
    manifest = {"generated": datetime.now(timezone.utc).isoformat(), "files": {}}

    missing = []
    for fname in sorted(PHASE1_OUTPUTS):
        path = os.path.join(CATALOGS_DIR, fname)
        if os.path.exists(path):
            manifest["files"][fname] = file_stats(path)
            print(f"  {fname}: {manifest['files'][fname]['md5']}")
        else:
            missing.append(fname)
            print(f"  {fname}: MISSING")

    if missing:
        print(f"\nWARNING: {len(missing)} contract file(s) missing: {missing}")

    out_path = os.path.join(CATALOGS_DIR, "corpus_manifest.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
