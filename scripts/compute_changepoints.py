"""Apply multi-detector change point analysis to divergence time series.

Reads divergence CSVs (one per method or legacy combined format) and applies
three families of change point detectors from the `ruptures` library:
  - PELT (Pruned Exact Linear Time)
  - Dynp (Dynamic Programming, approximating BOCPD)
  - KernelCPD (Kernel-based Change Point Detection)

Outputs:
  --output path → breaks table (method, channel, window, hyperparams, detector, ...)
  {stem}_convergence.csv → convergence analysis across methods

Usage:
    python3 scripts/compute_changepoints.py \
        --output content/tables/tab_changepoints.csv \
        --input content/tables/tab_div_*.csv

    # Legacy format also works:
    python3 scripts/compute_changepoints.py \
        --output content/tables/tab_changepoints.csv \
        --input content/tables/tab_semantic_divergence.csv \
               content/tables/tab_lexical_divergence.csv \
               content/tables/tab_citation_divergence.csv
"""

import glob
import os
import sys

import pandas as pd
import ruptures

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline_loaders import load_analysis_config
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_changepoints")

# Minimum non-NaN points required to fit a detector
MIN_POINTS = 5

# Channel classification by method prefix
METHOD_CHANNEL = {
    "S": "semantic",
    "L": "lexical",
    "G": "citation",
}


def _infer_channel(method_name):
    """Infer channel from method name prefix."""
    for prefix, channel in METHOD_CHANNEL.items():
        if method_name.startswith(prefix):
            return channel
    return "unknown"


def _extract_method_from_path(path):
    """Extract method name from tab_div_{method}.csv filename."""
    basename = os.path.splitext(os.path.basename(path))[0]
    if basename.startswith("tab_div_"):
        return basename[len("tab_div_"):]
    return None


def _load_divergence_tables(input_paths):
    """Load divergence CSVs, handling both new and legacy formats.

    Returns a DataFrame with columns:
        method, channel, year, window, hyperparams, value
    """
    frames = []
    for path in input_paths:
        if not os.path.exists(path):
            log.warning("File not found: %s", path)
            continue
        df = pd.read_csv(path)

        # New format: no 'method' column, method from filename
        if "method" not in df.columns:
            method = _extract_method_from_path(path)
            if method is None:
                log.warning("Cannot determine method from filename: %s", path)
                continue
            df["method"] = method

        # Ensure channel column exists
        if "channel" not in df.columns:
            df["channel"] = df["method"].apply(_infer_channel)

        expected = {"year", "method", "channel", "window", "hyperparams", "value"}
        if not expected.issubset(set(df.columns)):
            log.warning("Skipping %s: missing columns %s",
                        path, expected - set(df.columns))
            continue
        frames.append(df[list(expected)])

    if not frames:
        return pd.DataFrame(columns=["method", "channel", "year",
                                      "window", "hyperparams", "value"])
    return pd.concat(frames, ignore_index=True)


def _interpolate_signal(values):
    """Interpolate NaN values in a signal for ruptures fitting.

    Returns (signal_array, year_index, valid_mask) or None if too few points.
    """
    s = pd.Series(values, dtype=float)
    non_null = s.dropna()
    if len(non_null) < MIN_POINTS:
        return None
    # Linear interpolation for internal NaNs
    s_interp = s.interpolate(method="linear", limit_direction="both")
    return s_interp.values


def _run_pelt(signal, penalties, min_size=2):
    """Run PELT detector with multiple penalties.

    Returns list of (detector_params, break_indices).
    """
    results = []
    algo = ruptures.Pelt(model="rbf", min_size=min_size, jump=1)
    algo.fit(signal)
    for pen in penalties:
        try:
            bkps = algo.predict(pen=pen)
            # ruptures returns indices (1-indexed positions), last is len(signal)
            bkps = [b for b in bkps if b < len(signal)]
            results.append((f"pen={pen}", bkps))
        except Exception as e:
            log.debug("PELT pen=%s failed: %s", pen, e)
            results.append((f"pen={pen}", []))
    return results


def _run_dynp(signal, n_bkps_list, min_size=2):
    """Run Dynp detector with multiple n_bkps values.

    Returns list of (detector_params, break_indices).
    """
    results = []
    algo = ruptures.Dynp(model="l2", min_size=min_size, jump=1)
    algo.fit(signal)
    for k in n_bkps_list:
        try:
            bkps = algo.predict(n_bkps=k)
            bkps = [b for b in bkps if b < len(signal)]
            results.append((f"n_bkps={k}", bkps))
        except Exception as e:
            log.debug("Dynp n_bkps=%s failed: %s", k, e)
            results.append((f"n_bkps={k}", []))
    return results


def _run_kernel_cpd(signal, penalties, min_size=2):
    """Run KernelCPD detector with multiple penalties.

    Returns list of (detector_params, break_indices).
    """
    results = []
    algo = ruptures.KernelCPD(kernel="rbf", min_size=min_size, jump=1)
    algo.fit(signal)
    for pen in penalties:
        try:
            bkps = algo.predict(pen=pen)
            bkps = [b for b in bkps if b < len(signal)]
            results.append((f"pen={pen}", bkps))
        except Exception as e:
            log.debug("KernelCPD pen=%s failed: %s", pen, e)
            results.append((f"pen={pen}", []))
    return results


def compute_breaks(div_df, pelt_penalties, dynp_n_bkps=None):
    """Apply all detectors to all (method, window, hyperparams) groups.

    Parameters
    ----------
    div_df : DataFrame
        Divergence data with columns: method, channel, year, window,
        hyperparams, value
    pelt_penalties : list of int/float
        Penalties for PELT and KernelCPD.
    dynp_n_bkps : list of int, optional
        Number of breakpoints for Dynp. Default: [1, 2, 3].

    Returns
    -------
    DataFrame with columns:
        method, channel, window, hyperparams, detector, detector_params,
        break_years

    """
    if dynp_n_bkps is None:
        dynp_n_bkps = [1, 2, 3]

    rows = []
    groups = div_df.groupby(["method", "channel", "window", "hyperparams"],
                            dropna=False)
    n_groups = len(groups)
    log.info("Processing %d (method, window, hyperparams) groups", n_groups)

    for (method, channel, window, hp), grp in groups:
        grp = grp.sort_values("year")
        years = grp["year"].values
        values = grp["value"].values

        signal = _interpolate_signal(values)
        if signal is None:
            log.debug("Skipping %s w=%s hp=%s: too few non-NaN points",
                      method, window, hp)
            continue

        # Reshape for ruptures (n_samples, 1)
        sig = signal.reshape(-1, 1)

        def _idx_to_years(indices):
            """Convert ruptures break indices to years."""
            return sorted(int(years[i]) for i in indices if i < len(years))

        # PELT
        for params, bkps in _run_pelt(sig, pelt_penalties):
            break_yrs = _idx_to_years(bkps)
            rows.append({
                "method": method,
                "channel": channel,
                "window": str(window),
                "hyperparams": hp if pd.notna(hp) else "",
                "detector": "pelt",
                "detector_params": params,
                "break_years": ";".join(str(y) for y in break_yrs),
            })

        # Dynp (BOCPD approximation)
        for params, bkps in _run_dynp(sig, dynp_n_bkps):
            break_yrs = _idx_to_years(bkps)
            rows.append({
                "method": method,
                "channel": channel,
                "window": str(window),
                "hyperparams": hp if pd.notna(hp) else "",
                "detector": "dynp",
                "detector_params": params,
                "break_years": ";".join(str(y) for y in break_yrs),
            })

        # Kernel CPD
        for params, bkps in _run_kernel_cpd(sig, pelt_penalties):
            break_yrs = _idx_to_years(bkps)
            rows.append({
                "method": method,
                "channel": channel,
                "window": str(window),
                "hyperparams": hp if pd.notna(hp) else "",
                "detector": "kernel_cpd",
                "detector_params": params,
                "break_years": ";".join(str(y) for y in break_yrs),
            })

    return pd.DataFrame(rows)


_CONV_COLUMNS = ["year", "n_semantic", "n_lexical", "n_citation",
                 "n_total", "pct_total", "methods_detecting"]


def _parse_break_years(raw):
    """Parse semicolon-separated break years string into a set of ints."""
    if pd.isna(raw) or str(raw).strip() == "":
        return set()
    years = set()
    for y_str in str(raw).split(";"):
        y_str = y_str.strip()
        if y_str:
            try:
                years.add(int(float(y_str)))
            except ValueError:
                pass
    return years


def _count_detections(breaks_df, candidate_year, tolerance=1):
    """Count detections within ±tolerance of candidate_year, by channel."""
    counts = {"semantic": 0, "lexical": 0, "citation": 0}
    methods = set()
    for _, row in breaks_df.iterrows():
        row_years = _parse_break_years(row["break_years"])
        if any(abs(y - candidate_year) <= tolerance for y in row_years):
            channel = row["channel"]
            if channel in counts:
                counts[channel] += 1
            methods.add(row["method"])
    return counts, methods


def compute_convergence(breaks_df):
    """Build convergence table: for each candidate year, count detections.

    For each year detected by at least one (method x detector x params)
    combination, count how many combinations detect a break within +/-1 year,
    broken out by channel.

    Parameters
    ----------
    breaks_df : DataFrame
        Output of compute_breaks.

    Returns
    -------
    DataFrame with columns:
        year, n_semantic, n_lexical, n_citation, n_total, pct_total,
        methods_detecting

    """
    if breaks_df.empty:
        return pd.DataFrame(columns=_CONV_COLUMNS)

    all_years = set()
    for raw in breaks_df["break_years"]:
        all_years |= _parse_break_years(raw)

    if not all_years:
        return pd.DataFrame(columns=_CONV_COLUMNS)

    total_possible = len(breaks_df)
    rows = []
    for candidate_year in sorted(all_years):
        counts, methods = _count_detections(breaks_df, candidate_year)
        n_total = sum(counts.values())
        rows.append({
            "year": candidate_year,
            "n_semantic": counts["semantic"],
            "n_lexical": counts["lexical"],
            "n_citation": counts["citation"],
            "n_total": n_total,
            "pct_total": round(n_total / total_possible, 4) if total_possible > 0 else 0.0,
            "methods_detecting": ";".join(sorted(methods)),
        })

    return pd.DataFrame(rows)


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    # Load config
    cfg = load_analysis_config()
    div_cfg = cfg["divergence"]
    pelt_penalties = div_cfg.get("pelt_penalties", [1, 3, 5])
    dynp_n_bkps = [1, 2, 3]

    # Find input files
    if io_args.input:
        input_paths = io_args.input
    else:
        tables_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "content", "tables",
        )
        # Try new-style first
        input_paths = sorted(glob.glob(os.path.join(tables_dir, "tab_div_*.csv")))
        if not input_paths:
            # Fall back to legacy combined files
            input_paths = sorted(glob.glob(
                os.path.join(tables_dir, "tab_*_divergence.csv")
            ))
    log.info("Input files: %s", [os.path.basename(p) for p in input_paths])

    # Load divergence data
    div_df = _load_divergence_tables(input_paths)
    if div_df.empty:
        log.warning("No divergence data found; writing empty output")
        pd.DataFrame(columns=[
            "method", "channel", "window", "hyperparams",
            "detector", "detector_params", "break_years",
        ]).to_csv(io_args.output, index=False)
        return

    log.info("Loaded %d divergence rows across %d methods",
             len(div_df), div_df["method"].nunique())

    # Compute breaks
    breaks_df = compute_breaks(div_df, pelt_penalties, dynp_n_bkps)
    log.info("Computed %d break rows", len(breaks_df))

    # Save breaks table
    breaks_df.to_csv(io_args.output, index=False)
    log.info("Saved breaks table -> %s (%d rows)", io_args.output, len(breaks_df))

    log.info("Done.")


if __name__ == "__main__":
    main()
