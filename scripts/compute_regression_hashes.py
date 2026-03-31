"""Compute SHA-256 hashes of deterministic Phase 2 script outputs.

Runs each registered script on the smoke fixture (100 rows), collects
output file hashes, and either saves a new golden baseline or compares
against an existing one.

Usage:
    # Generate golden hashes (first time or after intentional change):
    uv run python scripts/compute_regression_hashes.py --update-golden

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
        "args": ["--output", "content/figures/fig_bars.png"],
        "deps": [],
        "outputs": [
            "content/figures/fig_bars.png",
        ],
    },
    {
        "name": "plot_fig1_bars_v1",
        "script": "plot_fig1_bars.py",
        "args": [
            "--output", "content/figures/fig_bars_v1.png",
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
        "args": ["--output", "content/figures/fig_breaks.png"],
        "deps": ["compute_breakpoints"],
        "outputs": [
            "content/figures/fig_breaks.png",
        ],
    },
    {
        "name": "plot_fig2_composition",
        "script": "plot_fig2_composition.py",
        "args": [
            "--output", "content/figures/fig_composition.png",
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


def _redirect_args(args: list[str], output_root: Path) -> list[str]:
    """Rewrite --output and --input paths to use output_root instead of ROOT.

    Paths that start with a known relative prefix (content/, tests/) are
    redirected to output_root/<relpath>. Absolute paths under ROOT are
    converted to relative first.
    """
    result: list[str] = []
    for arg in args:
        p = Path(arg)
        # Absolute path under ROOT → make relative
        if p.is_absolute():
            try:
                rel = p.relative_to(ROOT)
                arg = str(rel)
            except ValueError:
                result.append(arg)
                continue
        # Relative path starting with content/ or tests/ → redirect
        if arg.startswith(("content/", "tests/")):
            redirected = output_root / arg
            redirected.parent.mkdir(parents=True, exist_ok=True)
            result.append(str(redirected))
        else:
            result.append(arg)
    return result


def _run_one(
    entry: dict, env: dict, output_root: Path,
) -> tuple[str, dict[str, str]]:
    """Run one script, return (name, {file: hash}) or raise on failure.

    output_root controls where --output paths are redirected. When it equals
    ROOT, behavior is unchanged (CLI / --update-golden path).
    """
    name = entry["name"]
    script = str(SCRIPTS_DIR / entry["script"])
    redirected_args = _redirect_args(entry["args"], output_root)
    proc = subprocess.run(
        [sys.executable, script, *redirected_args],
        capture_output=True, text=True, env=env, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed (exit {proc.returncode}):\n{proc.stderr[:500]}")
    hashes: dict[str, str] = {}
    for rel_path in entry["outputs"]:
        abs_path = output_root / rel_path
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


def _stage_intermediates(
    wave_results: dict[str, dict[str, str]],
    output_root: Path,
) -> list[tuple[Path, Path | None]]:
    """Copy Wave N outputs into content/ dirs so Wave N+1 scripts can read them.

    Wave 2+ scripts hardcode reads from BASE_DIR/content/tables/ (via
    pipeline_loaders.BASE_DIR). When output_root != ROOT we must place
    intermediate CSV/JSON files where those scripts expect them.

    Returns list of (dst_path, backup_path_or_None) for restoration.
    If the destination already existed, it is backed up to a temp file
    so it can be restored with original content AND timestamps.
    """
    import tempfile

    if output_root == ROOT:
        return []  # no redirection — files are already in place

    staged: list[tuple[Path, Path | None]] = []
    for file_hashes in wave_results.values():
        for rel_path in file_hashes:
            src = output_root / rel_path
            dst = ROOT / rel_path
            if src.exists() and src.suffix in (".csv", ".json"):
                # Back up original file (preserving timestamps) for restoration
                backup: Path | None = None
                if dst.exists():
                    fd, tmp_name = tempfile.mkstemp(
                        prefix="staged_backup_", suffix=dst.suffix,
                    )
                    os.close(fd)
                    backup = Path(tmp_name)
                    shutil.copy2(dst, backup)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                staged.append((dst, backup))
    return staged


def _cleanup_intermediates(staged: list[tuple[Path, Path | None]]) -> None:
    """Restore or remove intermediate files that were staged for Wave 2+ reads."""
    for path, backup in staged:
        if backup is not None:
            # Restore original file with original timestamps
            shutil.copy2(backup, path)
            backup.unlink()
        elif path.exists():
            path.unlink()


def run_and_hash(
    output_root: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Run scripts in parallel waves, return {script_name: {file: sha256}}.

    Parameters
    ----------
    output_root : Path or None
        Directory used as prefix for script --output paths.
        Defaults to ROOT (current behavior for CLI / --update-golden).

    Wave 1 (independent scripts) runs in parallel.
    Wave 2 (dependent scripts) runs in parallel after wave 1.
    Between waves, intermediate outputs (CSV/JSON) are staged into
    content/ so that Wave 2 scripts can read them via hardcoded paths.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if output_root is None:
        output_root = ROOT

    # Ensure output directories exist
    (output_root / "content" / "tables").mkdir(parents=True, exist_ok=True)
    (output_root / "content" / "figures").mkdir(parents=True, exist_ok=True)
    # build_het_core writes to tests/fixtures/smoke/catalogs/
    (output_root / "tests" / "fixtures" / "smoke" / "catalogs").mkdir(
        parents=True, exist_ok=True,
    )

    env = _smoke_env()
    results: dict[str, dict[str, str]] = {}
    waves = _resolve_waves()
    staged: list[tuple[Path, Path | None]] = []

    try:
        for i, wave in enumerate(waves):
            log.info("Wave %d: %s", i + 1, [e["name"] for e in wave])
            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                futures = {
                    pool.submit(_run_one, e, env, output_root): e["name"]
                    for e in wave
                }
                for future in as_completed(futures):
                    name, hashes = future.result()  # raises on failure
                    results[name] = hashes
                    log.info("  %s: %d outputs", name, len(hashes))
            # Stage intermediates for next wave's reads
            staged.extend(_stage_intermediates(results, output_root))
    finally:
        _cleanup_intermediates(staged)

    return results


def load_golden() -> dict[str, dict[str, str]]:
    """Load golden hashes from disk."""
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(
            f"Golden hashes not found at {GOLDEN_PATH}. "
            "Run with --update-golden to create the baseline."
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
    group.add_argument("--update-golden", action="store_true",
                       help="Generate and save golden hashes")
    group.add_argument("--check", action="store_true",
                       help="Compare current outputs against golden hashes")
    group.add_argument("--dump", action="store_true",
                       help="Print current hashes to stdout (no file I/O)")
    args = parser.parse_args()

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="regression_"))
    try:
        current = run_and_hash(output_root=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if args.dump:
        print(json.dumps(current, indent=2, sort_keys=True))
        return

    if args.update_golden:
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
