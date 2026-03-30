"""Historical regression analysis: run Phase 2 scripts at past commits.

For each commit in a given range, checks out the code in a worktree,
runs registered scripts on the smoke fixture, and records output hashes.
Compares hashes across commits to find where outputs changed.

Usage:
    uv run python scripts/compute_regression_history.py --commits <sha1> <sha2> ...
    uv run python scripts/compute_regression_history.py --range <start>..<end>
    uv run python scripts/compute_regression_history.py --since-smoke

Output: prints a table of (commit, script, output, hash) and flags changes.
"""

import hashlib
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from utils import get_logger

log = get_logger("compute_regression_history")

# ---------------------------------------------------------------------------
# Paths (relative to this script's location in the repo)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "smoke"

# Scripts to test and their expected outputs (relative to repo root).
# Only scripts that existed since the smoke pipeline was added (bfa63c7).
SCRIPTS = [
    {
        "name": "compute_breakpoints",
        "script": "scripts/compute_breakpoints.py",
        "args": [],
        "outputs": [
            "content/tables/tab_breakpoints.csv",
            "content/tables/tab_breakpoint_robustness.csv",
        ],
    },
    {
        "name": "compute_clusters",
        "script": "scripts/compute_clusters.py",
        "args": [],
        "outputs": [
            "content/tables/tab_alluvial.csv",
            "content/tables/cluster_labels.json",
        ],
    },
]

# plot_fig1_bars is excluded from history: --output flag was added later
# (c66ded0), so older commits don't support it. The two compute scripts
# are the ones whose output stability matters most.

SIGNIFICANT_DIGITS = 8


def _canonicalize_csv(path: Path) -> bytes:
    """Round floats in CSV to absorb insignificant platform differences."""
    with open(path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for row in rows:
        canonical = []
        for cell in row:
            try:
                val = float(cell)
                canonical.append("0.0" if val == 0.0
                                 else f"{val:.{SIGNIFICANT_DIGITS}g}")
            except (ValueError, OverflowError):
                canonical.append(cell)
        writer.writerow(canonical)
    return buf.getvalue().encode("utf-8")


def _canonicalize_json(path: Path) -> bytes:
    """Round floats in JSON."""
    import math

    def _round(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return obj
            return 0.0 if obj == 0.0 else float(f"{obj:.{SIGNIFICANT_DIGITS}g}")
        if isinstance(obj, dict):
            return {k: _round(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_round(v) for v in obj]
        return obj

    with open(path) as f:
        data = json.load(f)
    return json.dumps(_round(data), sort_keys=True,
                       separators=(",", ":")).encode("utf-8")


def _hash_file(path: Path) -> str:
    """Hash output file with format-aware canonicalization."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        data = _canonicalize_csv(path)
    elif suffix == ".json":
        data = _canonicalize_json(path)
    else:
        data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _run_at_commit(sha: str, worktree_base: Path) -> dict[str, dict[str, str]]:
    """Checkout commit in a worktree, run scripts, return hashes."""
    wt_path = worktree_base / f"wt-{sha[:8]}"

    # Create worktree
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt_path), sha],
        capture_output=True, text=True, check=True, cwd=str(ROOT),
    )

    try:
        # Copy smoke fixture into worktree (it may not exist at old commits)
        wt_fixture = wt_path / "tests" / "fixtures" / "smoke"
        wt_fixture.mkdir(parents=True, exist_ok=True)
        for f in FIXTURE_DIR.iterdir():
            if not f.name.startswith("."):
                shutil.copy2(f, wt_fixture / f.name)

        # Ensure output dirs exist
        (wt_path / "content" / "tables").mkdir(parents=True, exist_ok=True)
        (wt_path / "content" / "figures").mkdir(parents=True, exist_ok=True)

        # Sync dependencies in worktree
        sync = subprocess.run(
            ["uv", "sync", "--quiet"],
            capture_output=True, text=True, cwd=str(wt_path), timeout=120,
        )
        if sync.returncode != 0:
            print(f"  WARNING: uv sync failed at {sha[:8]}, trying without sync")

        env = {
            **os.environ,
            "CLIMATE_FINANCE_DATA": str(wt_fixture),
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": "0",
            "MPLBACKEND": "Agg",
        }

        results: dict[str, dict[str, str]] = {}

        for entry in SCRIPTS:
            name = entry["name"]
            script_path = wt_path / entry["script"]

            if not script_path.exists():
                results[name] = {"__error__": "script not found"}
                continue

            proc = subprocess.run(
                ["uv", "run", "python", str(script_path), *entry["args"]],
                capture_output=True, text=True, env=env, timeout=180,
                cwd=str(wt_path),
            )

            if proc.returncode != 0:
                results[name] = {"__error__": proc.stderr[:200]}
                continue

            hashes: dict[str, str] = {}
            for rel_path in entry["outputs"]:
                abs_path = wt_path / rel_path
                if abs_path.exists():
                    hashes[rel_path] = _hash_file(abs_path)
                else:
                    hashes[rel_path] = "__missing__"
            results[name] = hashes

        return results

    finally:
        # Clean up worktree
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt_path)],
            capture_output=True, text=True, cwd=str(ROOT),
        )


def _get_commit_info(sha: str) -> str:
    """Return short sha + first line of commit message."""
    result = subprocess.run(
        ["git", "log", "--format=%h %s", "-1", sha],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.stdout.strip()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Historical regression analysis across commits"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--commits", nargs="+",
                       help="Specific commit SHAs to test")
    group.add_argument("--range", type=str,
                       help="Git range (e.g., bfa63c7..HEAD)")
    group.add_argument("--since-smoke", action="store_true",
                       help="Test all merge commits since smoke pipeline was added")
    args = parser.parse_args()

    if args.since_smoke:
        # Smoke pipeline was added at bfa63c7 (merged as 0fdd302)
        result = subprocess.run(
            ["git", "log", "--oneline", "--merges", "0fdd302..HEAD"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        commits = [line.split()[0] for line in result.stdout.strip().split("\n")
                    if line.strip()]
        # Add the smoke pipeline merge itself as baseline
        commits.append("0fdd302")
        commits.reverse()  # oldest first
    elif args.range:
        result = subprocess.run(
            ["git", "log", "--oneline", "--merges", args.range],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        commits = [line.split()[0] for line in result.stdout.strip().split("\n")
                    if line.strip()]
        commits.reverse()
    else:
        commits = args.commits

    print(f"Testing {len(commits)} commits...")
    print()

    tmp_base = Path(tempfile.mkdtemp(prefix="regression_history_"))

    all_results: list[tuple[str, str, dict]] = []
    try:
        for sha in commits:
            info = _get_commit_info(sha)
            print(f"  {info} ...", end=" ", flush=True)
            try:
                hashes = _run_at_commit(sha, tmp_base)
                all_results.append((sha, info, hashes))
                n_ok = sum(
                    1 for h in hashes.values()
                    for v in h.values()
                    if v not in ("__missing__", "__error__") and not v.startswith("__")
                )
                n_err = sum(1 for h in hashes.values() if "__error__" in h)
                if n_err:
                    print(f"  {n_ok} hashed, {n_err} errors")
                else:
                    print(f"  {n_ok} outputs hashed")
            except Exception as e:
                print(f"  FAILED: {e}")
                all_results.append((sha, info, {"__error__": str(e)}))
    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)

    # --- Report ---
    print()
    print("=" * 72)
    print("REGRESSION HISTORY REPORT")
    print("=" * 72)

    if len(all_results) < 2:
        print("Need at least 2 commits to compare.")
        return

    # Compare consecutive pairs
    changes_found = 0
    for i in range(1, len(all_results)):
        prev_sha, prev_info, prev_hashes = all_results[i - 1]
        cur_sha, cur_info, cur_hashes = all_results[i]

        diffs = []
        for script in sorted(set(list(prev_hashes.keys()) + list(cur_hashes.keys()))):
            if script.startswith("__"):
                continue
            prev_h = prev_hashes.get(script, {})
            cur_h = cur_hashes.get(script, {})
            if "__error__" in prev_h or "__error__" in cur_h:
                continue
            for f in sorted(set(list(prev_h.keys()) + list(cur_h.keys()))):
                pv = prev_h.get(f, "__missing__")
                cv = cur_h.get(f, "__missing__")
                if pv != cv:
                    diffs.append((script, f, pv[:12], cv[:12]))

        if diffs:
            changes_found += len(diffs)
            print(f"\n  {prev_info}")
            print(f"→ {cur_info}")
            for script, f, old, new in diffs:
                print(f"  CHANGED  {script} / {os.path.basename(f)}")
                print(f"           {old}... → {new}...")

    if changes_found == 0:
        print("\nNo output changes detected across all tested commits.")
    else:
        print(f"\n{changes_found} output change(s) detected across "
              f"{len(all_results)} commits.")

    # Final hashes table
    print()
    print("-" * 72)
    print("FINAL HASHES (most recent commit)")
    print("-" * 72)
    _, info, hashes = all_results[-1]
    print(f"Commit: {info}")
    for script, files in sorted(hashes.items()):
        if script.startswith("__"):
            continue
        for f, h in sorted(files.items()):
            print(f"  {script:25s}  {os.path.basename(f):40s}  {h[:16]}...")


if __name__ == "__main__":
    main()
