"""Compute SHA-256 hashes of deterministic Phase 2 script outputs.

Runs each registered script on the smoke fixture (100 rows), collects
output file hashes, and either saves a new golden baseline or compares
against an existing one.

Usage:
    # Generate golden hashes (first time or after intentional change):
    uv run python scripts/compute_regression_hashes.py --save-golden

    # Compare current outputs against golden baseline:
    uv run python scripts/compute_regression_hashes.py --check

    # Dump current hashes to stdout (no file I/O):
    uv run python scripts/compute_regression_hashes.py --dump

Environment: PYTHONHASHSEED=0, SOURCE_DATE_EPOCH=0, MPLBACKEND=Agg,
CLIMATE_FINANCE_DATA pointed at the smoke fixture.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from utils import get_logger

log = get_logger("compute_regression_hashes")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "smoke"
GOLDEN_PATH = FIXTURE_DIR / "golden_hashes.json"
SCRIPTS_DIR = ROOT / "scripts"
CONTENT_DIR = ROOT / "content"
TABLES_DIR = CONTENT_DIR / "tables"
FIGURES_DIR = CONTENT_DIR / "figures"

# ---------------------------------------------------------------------------
# Script registry: (script, args, output_files)
#
# Each entry lists the script to run, its CLI args, and the output files
# it produces (relative to ROOT). Order matters: dependencies first.
# ---------------------------------------------------------------------------

REGISTRY: list[dict] = [
    # --- Wave 1: independent (no deps, run in parallel) ---
    {
        "name": "compute_breakpoints",
        "script": "compute_breakpoints.py",
        "args": ["--output", "content/tables/tab_breakpoints.csv"],
        "deps": [],
        "outputs": [
            "content/tables/tab_breakpoints.csv",
        ],
    },
    {
        "name": "compute_breakpoint_robustness",
        "script": "compute_breakpoints.py",
        "args": ["--output", "content/tables/tab_breakpoint_robustness.csv",
                 "--robustness"],
        "deps": [],
        "outputs": [
            "content/tables/tab_breakpoint_robustness.csv",
        ],
    },
    {
        "name": "compute_clusters",
        "script": "compute_clusters.py",
        "args": ["--output", "content/tables/tab_alluvial.csv"],
        "deps": [],
        "outputs": [
            "content/tables/tab_alluvial.csv",
            "content/tables/cluster_labels.json",
        ],
    },
    {
        "name": "plot_fig1_bars",
        "script": "plot_fig1_bars.py",
        "args": ["--output", str(FIGURES_DIR / "fig_bars.png")],
        "deps": [],
        "outputs": [
            "content/figures/fig_bars.png",
        ],
    },
    {
        "name": "plot_fig1_bars_v1",
        "script": "plot_fig1_bars.py",
        "args": [
            "--output", str(FIGURES_DIR / "fig_bars_v1.png"),
            "--v1-only",
        ],
        "deps": [],
        "outputs": [
            "content/figures/fig_bars_v1.png",
        ],
    },
    {
        "name": "build_het_core",
        "script": "build_het_core.py",
        "args": ["--output", "tests/fixtures/smoke/catalogs/het_mostcited_50.csv"],
        "deps": [],
        "outputs": [
            "tests/fixtures/smoke/catalogs/het_mostcited_50.csv",
        ],
    },
    # --- Wave 2: depend on compute_* outputs ---
    {
        "name": "plot_fig2_breaks",
        "script": "plot_fig2_breaks.py",
        "args": [],
        "deps": ["compute_breakpoints"],
        "outputs": [
            "content/figures/fig_breaks.png",
        ],
    },
    {
        "name": "plot_fig2_composition",
        "script": "plot_fig2_composition.py",
        "args": [
            "--output", str(FIGURES_DIR / "fig_composition.png"),
        ],
        "deps": ["compute_clusters"],
        "outputs": [
            "content/figures/fig_composition.png",
        ],
    },
    {
        "name": "plot_fig_alluvial",
        "script": "plot_fig_alluvial.py",
        "args": ["--output", "content/figures/fig_alluvial.png"],
        "deps": ["compute_clusters"],
        "outputs": [
            "content/figures/fig_alluvial.png",
        ],
    },
    {
        "name": "plot_fig_breakpoints",
        "script": "plot_fig_breakpoints.py",
        "args": ["--output", "content/figures/fig_breakpoints.png"],
        "deps": ["compute_breakpoints", "compute_breakpoint_robustness",
                 "compute_clusters"],
        "outputs": [
            "content/figures/fig_breakpoints.png",
        ],
    },
]

# Scripts excluded from regression testing (exit gracefully but produce
# no meaningful output on 100 rows):
# - compute_lexical: no robust breakpoints → empty output (exits 0)
# - analyze_bimodality: too few pole papers → exits 0
# - plot_fig_seed_axis: not enough core papers for violins
# - plot_fig45_pca_scatter: no bimodal PCs at 100 rows (exits 0)
# - export_corpus_table: needs unified_works.csv (Phase 1 artifact)


def _smoke_env() -> dict[str, str]:
    """Environment dict for deterministic smoke runs."""
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": str(FIXTURE_DIR),
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
        "MPLBACKEND": "Agg",
    }


def _sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


# Number of significant digits retained when hashing numeric data.
# Low enough to absorb floating-point noise across platforms/compilers,
# high enough to catch real regressions in computed values.
SIGNIFICANT_DIGITS = 8


def _canonicalize_csv(path: Path) -> bytes:
    """Parse CSV, round floats, return canonical UTF-8 bytes.

    Absorbs insignificant floating-point differences (e.g., 0.123456789
    vs 0.12345679) that would cause spurious hash mismatches across
    platforms or numpy/scipy minor versions.
    """
    import csv
    import io

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
                # Round to N significant digits
                if val == 0.0:
                    canonical.append("0.0")
                else:
                    canonical.append(f"{val:.{SIGNIFICANT_DIGITS}g}")
            except (ValueError, OverflowError):
                canonical.append(cell)
        writer.writerow(canonical)
    return buf.getvalue().encode("utf-8")


def _canonicalize_json(path: Path) -> bytes:
    """Parse JSON, round floats, return canonical UTF-8 bytes."""
    import math

    def _round_floats(obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return obj
            if obj == 0.0:
                return 0.0
            return float(f"{obj:.{SIGNIFICANT_DIGITS}g}")
        if isinstance(obj, dict):
            return {k: _round_floats(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_round_floats(v) for v in obj]
        return obj

    with open(path) as f:
        data = json.load(f)
    canonical = _round_floats(data)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_output(path: Path) -> str:
    """Hash an output file, using format-aware canonicalization.

    CSV/JSON: parse, round floats to SIGNIFICANT_DIGITS, re-serialize.
    Everything else (PNG, etc.): raw binary hash.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _sha256_bytes(_canonicalize_csv(path))
    if suffix == ".json":
        return _sha256_bytes(_canonicalize_json(path))
    # Binary files (PNG, etc.): exact hash
    with open(path, "rb") as f:
        return _sha256_bytes(f.read())


def _backup_outputs() -> dict[str, Path | None]:
    """Back up existing output files that scripts will overwrite."""
    import tempfile
    backup_dir = Path(tempfile.mkdtemp(prefix="regression_backup_"))
    backups: dict[str, Path | None] = {}
    for entry in REGISTRY:
        for rel_path in entry["outputs"]:
            abs_path = ROOT / rel_path
            if abs_path.exists():
                dst = backup_dir / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(abs_path, dst)
                backups[rel_path] = dst
            else:
                backups[rel_path] = None
    backups["__dir__"] = backup_dir
    return backups


def _restore_outputs(backups: dict[str, Path | None]) -> None:
    """Restore backed-up files and clean up temp dir."""
    backup_dir = backups.pop("__dir__", None)
    for rel_path, backup_path in backups.items():
        abs_path = ROOT / rel_path
        if backup_path is not None:
            shutil.copy2(backup_path, abs_path)
        elif abs_path.exists():
            # File was created by regression run but didn't exist before
            abs_path.unlink()
    if backup_dir and backup_dir.exists():
        shutil.rmtree(backup_dir)


def _run_one(entry: dict, env: dict) -> tuple[str, dict[str, str]]:
    """Run one script, return (name, {file: hash}) or raise on failure."""
    name = entry["name"]
    script = str(SCRIPTS_DIR / entry["script"])
    proc = subprocess.run(
        [sys.executable, script, *entry["args"]],
        capture_output=True, text=True, env=env, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed (exit {proc.returncode}):\n{proc.stderr[:500]}")
    hashes: dict[str, str] = {}
    for rel_path in entry["outputs"]:
        abs_path = ROOT / rel_path
        if not abs_path.exists():
            raise FileNotFoundError(f"{name}: missing output {rel_path}")
        hashes[rel_path] = _hash_output(abs_path)
    return name, hashes


def _resolve_waves() -> list[list[dict]]:
    """Group REGISTRY entries into waves respecting deps."""
    done: set[str] = set()
    remaining = list(REGISTRY)
    waves: list[list[dict]] = []
    while remaining:
        wave = [e for e in remaining if all(d in done for d in e["deps"])]
        if not wave:
            names = [e["name"] for e in remaining]
            raise RuntimeError(f"Circular dependency in REGISTRY: {names}")
        waves.append(wave)
        done.update(e["name"] for e in wave)
        remaining = [e for e in remaining if e["name"] not in done]
    return waves


def run_and_hash() -> dict[str, dict[str, str]]:
    """Run scripts in parallel waves, return {script_name: {file: sha256}}.

    Wave 1 (5 scripts, no deps) runs in parallel.
    Wave 2 (4 scripts, depend on wave 1) runs in parallel after wave 1.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    env = _smoke_env()
    results: dict[str, dict[str, str]] = {}
    waves = _resolve_waves()

    for i, wave in enumerate(waves):
        log.info("Wave %d: %s", i + 1, [e["name"] for e in wave])
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futures = {pool.submit(_run_one, e, env): e["name"] for e in wave}
            for future in as_completed(futures):
                name, hashes = future.result()  # raises on failure
                results[name] = hashes
                log.info("  %s: %d outputs", name, len(hashes))

    return results


def load_golden() -> dict[str, dict[str, str]]:
    """Load golden hashes from disk."""
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(
            f"Golden hashes not found at {GOLDEN_PATH}. "
            "Run with --save-golden to create the baseline."
        )
    with open(GOLDEN_PATH) as f:
        return json.load(f)


def save_golden(hashes: dict[str, dict[str, str]]) -> None:
    """Save golden hashes to disk."""
    with open(GOLDEN_PATH, "w") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)
        f.write("\n")
    log.info("Golden hashes saved to %s", GOLDEN_PATH)


def compare(current: dict, golden: dict) -> list[str]:
    """Compare current hashes against golden baseline. Return list of diffs."""
    diffs: list[str] = []

    all_scripts = sorted(set(list(current.keys()) + list(golden.keys())))
    for script in all_scripts:
        if script not in golden:
            diffs.append(f"NEW script: {script}")
            continue
        if script not in current:
            diffs.append(f"MISSING script: {script}")
            continue

        cur_files = current[script]
        gold_files = golden[script]
        all_files = sorted(set(list(cur_files.keys()) + list(gold_files.keys())))
        for f in all_files:
            if f not in gold_files:
                diffs.append(f"  {script}: NEW output {f}")
            elif f not in cur_files:
                diffs.append(f"  {script}: MISSING output {f}")
            elif cur_files[f] != gold_files[f]:
                diffs.append(
                    f"  {script}: CHANGED {f}\n"
                    f"    golden:  {gold_files[f][:16]}...\n"
                    f"    current: {cur_files[f][:16]}..."
                )

    return diffs


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Regression testing via output hashing"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--save-golden", action="store_true",
                       help="Generate and save golden hashes")
    group.add_argument("--check", action="store_true",
                       help="Compare current outputs against golden hashes")
    group.add_argument("--dump", action="store_true",
                       help="Print current hashes to stdout (no file I/O)")
    args = parser.parse_args()

    backups = _backup_outputs()
    try:
        current = run_and_hash()
    finally:
        _restore_outputs(backups)

    if args.dump:
        print(json.dumps(current, indent=2, sort_keys=True))
        return

    if args.save_golden:
        save_golden(current)
        print(f"Golden hashes saved ({sum(len(v) for v in current.values())} files)")
        return

    # --check
    golden = load_golden()
    diffs = compare(current, golden)
    if not diffs:
        print("OK — all outputs match golden hashes.")
    else:
        print(f"REGRESSION — {len(diffs)} difference(s):")
        for d in diffs:
            print(d)
        sys.exit(1)


if __name__ == "__main__":
    main()
