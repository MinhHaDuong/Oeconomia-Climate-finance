"""Sensitivity grid: 4 windows × 4 gaps × 5 PCA dims, S2 energy, R=3.

Produces tab_sensitivity_grid.csv consumed by plot_companion_sensitivity.py
and referenced in the §Sensitivity appendix of multilayer-detection.qmd.

Usage:
    uv run python scripts/compute_sensitivity_grid.py \
        --output content/tables/tab_sensitivity_grid.csv

Do NOT run on a local workstation — corpus is on padme. The Makefile
target companion-sensitivity is the intended entry point.
"""

import copy
import sys

import pandas as pd
from _divergence_io import get_min_papers, per_window_year_ranges
from _divergence_semantic import compute_s2_energy, load_semantic_data
from pipeline_io import save_csv
from pipeline_loaders import load_analysis_config
from schemas import SensitivityGridSchema
from script_io_args import parse_io_args, validate_io
from sklearn.decomposition import PCA
from utils import get_logger

log = get_logger("compute_sensitivity_grid")

FULL_DIM_SENTINEL = 1024  # dims == this value → no PCA reduction


def _count_window_papers(df, year, window, gap, side):
    """Count papers in a before or after window.

    side='before': [year - window, year - gap]
    side='after':  [year + gap, year + window]
    """
    if side == "before":
        mask = (df["year"] >= year - window) & (df["year"] <= year - gap)
    else:
        mask = (df["year"] >= year + gap) & (df["year"] <= year + window)
    return int(mask.sum())


def _run_one_cell(
    df, emb_proj, cfg_base, window, gap, r_replicates, base_seed, min_papers
):
    """Run R replicates for one (window, gap) cell and return raw rows.

    Returns list of dicts with year, window, value.
    """
    rows = []
    for r in range(r_replicates):
        cfg_r = copy.deepcopy(cfg_base)
        cfg_r["divergence"]["windows"] = [window]
        cfg_r["divergence"]["gap"] = gap
        cfg_r["divergence"]["random_seed"] = base_seed + r * 1000
        cfg_r["divergence"]["equal_n"] = True

        result = compute_s2_energy(df, emb_proj, cfg_r)
        if result.empty:
            continue
        for _, row in result.iterrows():
            rows.append(
                {
                    "year": int(row["year"]),
                    "window": str(window),
                    "replicate": r,
                    "value": float(row["value"]),
                }
            )
    return rows


def _median_replicates(rows, window):
    """Median across replicates per year for a given window."""
    if not rows:
        return pd.DataFrame(columns=["year", "window", "value"])
    df_r = pd.DataFrame(rows)
    medians = (
        df_r.groupby(["year", "window"])["value"]
        .median()
        .reset_index()
        .rename(columns={"value": "value"})
    )
    return medians


def _crossyear_zscore(values):
    """Standardise a series across years. Returns NaN series when std == 0."""
    vals = values.astype(float)
    mean_v = vals.mean()
    std_v = vals.std()
    if std_v == 0 or pd.isna(std_v):
        return pd.Series([float("nan")] * len(vals), index=vals.index)
    return (vals - mean_v) / std_v


def compute_grid(df, emb, cfg):
    """Run the full sensitivity grid computation.

    Parameters
    ----------
    df : pd.DataFrame
        Corpus with at least a ``year`` column.
    emb : np.ndarray
        Embedding matrix aligned with ``df``.
    cfg : dict
        Full analysis config (must contain ``sensitivity`` and
        ``divergence`` sub-dicts).

    Returns
    -------
    pd.DataFrame
        Rows with columns ``(model, dim, window, gap, year, method,
        z_score, n_before, n_after)``.  Empty DataFrame if no valid
        (window, gap, year) triples are found in the corpus.

    """
    sens = cfg["sensitivity"]
    windows = sens["windows"]
    gaps = sens["gaps"]
    dims = sens["dims"]
    r_replicates = sens["equal_n_r"]
    base_seed = cfg["divergence"]["random_seed"]

    log.info(
        "Sensitivity grid: %d windows × %d gaps × %d dims × R=%d",
        len(windows),
        len(gaps),
        len(dims),
        r_replicates,
    )

    min_papers = get_min_papers(method=None, cfg=cfg, n_works=len(df))
    log.info("min_papers=%d, corpus size=%d", min_papers, len(df))

    all_rows = []

    for dim in dims:
        log.info("=== dim=%d ===", dim)
        if dim < FULL_DIM_SENTINEL:
            actual_dim = min(dim, emb.shape[1])
            log.info("PCA-reducing to %d components", actual_dim)
            pca = PCA(n_components=actual_dim, random_state=base_seed)
            emb_proj = pca.fit_transform(emb)
        else:
            emb_proj = emb
            log.info("Using full embeddings (%d dims)", emb.shape[1])

        for gap in gaps:
            for window in windows:
                log.info("  window=%d gap=%d", window, gap)
                cell_rows = _run_one_cell(
                    df,
                    emb_proj,
                    copy.deepcopy(cfg),
                    window,
                    gap,
                    r_replicates,
                    base_seed,
                    min_papers,
                )
                medians = _median_replicates(cell_rows, window)
                if medians.empty:
                    log.warning(
                        "No results for dim=%d window=%d gap=%d", dim, window, gap
                    )
                    continue

                # Compute n_before / n_after for each year
                years_by_window = per_window_year_ranges(df, [window])

                for _, mrow in medians.iterrows():
                    y = int(mrow["year"])
                    n_before = _count_window_papers(
                        df, y, window, max(gap, 1) if gap == 0 else gap, "before"
                    )
                    n_after = _count_window_papers(
                        df, y, window, max(gap, 1) if gap == 0 else gap, "after"
                    )
                    all_rows.append(
                        {
                            "model": "bge-m3",
                            "dim": dim,
                            "window": str(window),
                            "gap": gap,
                            "year": y,
                            "method": "S2_energy",
                            "_value": float(mrow["value"]),
                            "n_before": n_before,
                            "n_after": n_after,
                        }
                    )

    if not all_rows:
        return pd.DataFrame(
            columns=[
                "model",
                "dim",
                "window",
                "gap",
                "year",
                "method",
                "z_score",
                "n_before",
                "n_after",
            ]
        )

    result = pd.DataFrame(all_rows)

    # Cross-year Z-score per (dim, window, gap) group
    result["z_score"] = float("nan")
    for keys, grp in result.groupby(["dim", "window", "gap"], sort=False):
        z = _crossyear_zscore(grp["_value"])
        result.loc[grp.index, "z_score"] = z.values

    result = result.drop(columns=["_value"])
    return result


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    cfg = load_analysis_config()
    df, emb = load_semantic_data(None)

    result = compute_grid(df, emb, cfg)

    if result.empty:
        log.error("No rows produced — check corpus and config")
        sys.exit(1)

    # Validate schema
    SensitivityGridSchema.validate(result)
    log.info("Schema validation passed (%d rows)", len(result))

    save_csv(result, io_args.output)


if __name__ == "__main__":
    sys.exit(main())
