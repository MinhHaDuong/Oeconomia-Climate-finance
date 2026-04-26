"""Compute the analytical null distribution for C2ST methods (ticket 0115).

For C2ST_embedding and C2ST_lexical, the null distribution under H0 (AUC = 0.5)
follows a closed-form Hanley-McNeil approximation:

    null_mean = 0.5
    null_std  = sqrt((n_before + n_after + 1) / (12 * n_before * n_after))

This is O(1) per (year, window) once sample counts are known — no permutations
or corpus loading of embeddings/texts needed.

Usage::

    uv run python scripts/compute_analytical_null.py \\
        --method C2ST_embedding \\
        --output content/tables/tab_analytical_null_C2ST_embedding.csv

    uv run python scripts/compute_analytical_null.py \\
        --method C2ST_lexical \\
        --output content/tables/tab_analytical_null_C2ST_lexical.csv

Output CSV matches NullModelSchema (schemas.py):
    year, window, observed, null_mean, null_std, z_score, p_value

observed, z_score, p_value are NaN (analytical null only supplies the
null distribution parameters, not the observed statistic).
"""

import argparse
import math
import sys

import pandas as pd
from _divergence_io import get_min_papers
from _divergence_lexical import load_lexical_data
from pipeline_loaders import load_analysis_config, load_analysis_corpus
from schemas import NullModelSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_analytical_null")

SUPPORTED_METHODS = ("C2ST_embedding", "C2ST_lexical")


# ---------------------------------------------------------------------------
# Hanley-McNeil formula
# ---------------------------------------------------------------------------


def c2st_analytical_null(n_before: int, n_after: int) -> tuple[float, float]:
    """Return (null_mean, null_std) for C2ST AUC under H0 (Hanley-McNeil 1982).

    Parameters
    ----------
    n_before : int
        Number of documents in the before-window.
    n_after : int
        Number of documents in the after-window.

    Returns
    -------
    (null_mean, null_std) : (float, float)
        null_mean = 0.5
        null_std  = sqrt((n_before + n_after + 1) / (12 * n_before * n_after))

    """
    null_mean = 0.5
    null_std = math.sqrt((n_before + n_after + 1) / (12 * n_before * n_after))
    return null_mean, null_std


# ---------------------------------------------------------------------------
# Window count iteration (metadata-only — no embeddings, no texts)
# ---------------------------------------------------------------------------


def _load_corpus_for_method(method: str) -> pd.DataFrame:
    """Load the appropriate corpus DataFrame for the given C2ST method.

    C2ST_lexical uses load_lexical_data() (dropna on abstract + year) to match
    the actual rows seen by iter_lexical_windows.  C2ST_embedding uses
    load_analysis_corpus() (no abstract filter) to match iter_semantic_windows.
    """
    if method == "C2ST_lexical":
        return load_lexical_data(None)
    # C2ST_embedding
    df, _ = load_analysis_corpus(with_embeddings=False)
    return df


def _iter_window_counts(method: str, cfg: dict):
    """Yield (year, window, n_before, n_after) for each valid (year, window) pair.

    Loads the corpus for the given method (no embeddings), applies the same
    year-range and gap logic as iter_semantic_windows / iter_lexical_windows,
    counts papers in each before/after window, and skips pairs that fall below
    min_papers.

    Parameters
    ----------
    method : str
        One of SUPPORTED_METHODS.  Determines which corpus loader is used so
        that n_before / n_after match the counts seen during MC null computation.
    cfg : dict
        Analysis config from load_analysis_config().

    Yields
    ------
    (y, w, n_before, n_after) : (int, int, int, int)

    """
    div_cfg = cfg["divergence"]
    windows = div_cfg["windows"]
    gap = div_cfg.get("gap", 1)
    equal_n = div_cfg.get("equal_n", False)
    min_papers = get_min_papers(method=method, cfg=cfg)

    df = _load_corpus_for_method(method)
    year_min = int(df["year"].min())
    year_max = int(df["year"].max())

    for w in windows:
        for y in range(year_min + w, year_max - w):
            mask_before = (df["year"] >= y - w) & (df["year"] <= y - gap)
            mask_after = (df["year"] >= y + gap) & (df["year"] <= y + w)
            n_b = int(mask_before.sum())
            n_a = int(mask_after.sum())

            if n_b < min_papers or n_a < min_papers:
                continue

            if equal_n:
                n_b = n_a = min(n_b, n_a)
                if n_b < min_papers:
                    continue

            yield y, w, n_b, n_a


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    io_args, extra = parse_io_args()

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--method",
        required=True,
        choices=list(SUPPORTED_METHODS),
        help="Method name: C2ST_embedding or C2ST_lexical",
    )
    args = parser.parse_args(extra)
    method = args.method

    validate_io(output=io_args.output)

    cfg = load_analysis_config()

    log.info("Computing analytical null for method=%s", method)

    rows = []
    for y, w, n_before, n_after in _iter_window_counts(method, cfg):
        null_mean, null_std = c2st_analytical_null(n_before, n_after)
        rows.append(
            {
                "year": y,
                "window": str(w),
                "observed": float("nan"),
                "null_mean": null_mean,
                "null_std": null_std,
                "z_score": float("nan"),
                "p_value": float("nan"),
            }
        )

    if not rows:
        log.warning(
            "No valid (year, window) pairs found — writing empty output to %s",
            io_args.output,
        )

    out_df = pd.DataFrame(
        rows,
        columns=[
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        ],
    )

    # Validate against schema before writing (strict=True, coerce=True)
    NullModelSchema.validate(out_df)

    out_df.to_csv(io_args.output, index=False)
    log.info("Wrote %d rows to %s", len(out_df), io_args.output)


if __name__ == "__main__":
    sys.exit(main())
