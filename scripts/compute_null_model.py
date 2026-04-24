"""Compute permutation Z-score null model for one divergence method.

For each (year, window) in the existing divergence CSV, permute labels
B times and recompute the statistic to build a null distribution.
Z(t) = (observed - mean_perm) / std_perm.

Usage:
    uv run python scripts/compute_null_model.py --method S2_energy \
        --output content/tables/tab_null_S2_energy.csv \
        --div-csv content/tables/tab_div_S2_energy.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        uv run python scripts/compute_null_model.py --method S2_energy \
        --output /tmp/tab_null_S2_energy.csv \
        --div-csv /tmp/tab_div_S2_energy.csv
"""

import argparse

import pandas as pd
from _permutation_c2st import (
    _run_c2st_embedding_permutations,
    _run_c2st_lexical_permutations,
)
from _permutation_citation import (
    _run_g1_permutations,
    _run_g5_permutations,
    _run_g6_permutations,
    _run_g8_permutations,
)
from _permutation_graph import (
    _run_g2_spectral_permutations,
    _run_g9_community_permutations,
)
from _permutation_io import (  # noqa: F401 — re-exports for backward compat
    _collect_permutation_rows,
    _finalize_row,
    _nan_row,
    _result_row,
    permutation_test,
)
from _permutation_lexical import (
    _make_lexical_statistic,  # noqa: F401 — re-export
    _run_lexical_permutations,
    run_l2_permutations,
    run_l3_permutations,
)
from _permutation_semantic import (
    _make_semantic_statistic,  # noqa: F401 — re-export
    _run_semantic_permutations,
)
from compute_divergence import METHODS
from pipeline_loaders import load_analysis_config
from schemas import NullModelSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_null_model")

# Methods supported for permutation testing
SUPPORTED_CHANNELS = {"semantic", "lexical", "citation"}


# ---------------------------------------------------------------------------
# Citation-channel dispatcher: method_name -> permutation driver.
# ---------------------------------------------------------------------------

_CITATION_PERMUTATION_DRIVERS = {
    "G1_pagerank": _run_g1_permutations,
    "G2_spectral": _run_g2_spectral_permutations,
    "G5_pref_attachment": _run_g5_permutations,
    "G6_entropy": _run_g6_permutations,
    "G8_betweenness": _run_g8_permutations,
    "G9_community": _run_g9_community_permutations,
}


def _run_citation_permutations(method_name, div_df, cfg, n_jobs=1):
    """Permutation test for citation-channel methods (G1-G9)."""
    from _divergence_citation import load_citation_data

    driver = _CITATION_PERMUTATION_DRIVERS.get(method_name)
    if driver is None:
        raise ValueError(
            f"No citation null-model driver for '{method_name}'. "
            f"Supported: {sorted(_CITATION_PERMUTATION_DRIVERS)}"
        )

    works, _, internal_edges = load_citation_data(None)
    return driver(works, internal_edges, div_df, cfg, n_jobs=n_jobs)


# ---------------------------------------------------------------------------
# Thin lexical stubs
# ---------------------------------------------------------------------------


def _run_l3_permutations(div_df, cfg):
    """Year-label permutation null model for L3.  See _permutation_lexical."""
    return run_l3_permutations(div_df, cfg)


def _run_l2_permutations(div_df, cfg):
    """Past/future pool-shuffle null model for L2.  See _permutation_lexical."""
    return run_l2_permutations(div_df, cfg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=METHODS.keys())
    # --div-csv is separate from --input because --input refers to the corpus
    # contract files (via CATALOGS_DIR), while --div-csv is a specific observed
    # divergence table this script compares against.
    parser.add_argument(
        "--div-csv",
        required=True,
        help="Path to the existing tab_div_{method}.csv",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="Parallel workers for CPU path (-1 = all cores, 1 = sequential)",
    )
    args = parser.parse_args(extra)

    method_name = args.method
    _, _, channel, _, _ = METHODS[method_name]

    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(
            f"Permutation test not yet supported for channel '{channel}'. "
            f"Supported: {SUPPORTED_CHANNELS}"
        )

    cfg = load_analysis_config()
    log.info("=== Null model: %s (channel=%s) ===", method_name, channel)

    # Load existing divergence CSV for year/window pairs
    div_df = pd.read_csv(args.div_csv)
    log.info("Loaded %d rows from %s", len(div_df), args.div_csv)

    import time

    t0 = time.perf_counter()

    if method_name.startswith("C2ST_"):
        # C2ST methods share channel names with S*/L* methods but use a
        # classifier statistic that is incompatible with _make_semantic_statistic
        # and _run_lexical_permutations.  Gate before the channel branches.
        if method_name == "C2ST_embedding":
            result = _run_c2st_embedding_permutations(div_df, cfg)
        else:
            result = _run_c2st_lexical_permutations(div_df, cfg)
    elif channel == "semantic":
        result = _run_semantic_permutations(
            method_name, div_df, cfg, n_jobs=args.n_jobs
        )
    elif channel == "lexical":
        if method_name == "L3":
            result = _run_l3_permutations(div_df, cfg)
        elif method_name == "L2":
            result = _run_l2_permutations(div_df, cfg)
        else:
            result = _run_lexical_permutations(method_name, div_df, cfg)
    elif channel == "citation":
        result = _run_citation_permutations(
            method_name, div_df, cfg, n_jobs=args.n_jobs
        )
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    elapsed = time.perf_counter() - t0
    log.info("Permutation testing completed in %.1fs", elapsed)

    # Validate contract
    NullModelSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
