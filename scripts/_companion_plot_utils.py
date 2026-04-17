"""Shared helpers for the companion-paper figure scripts (ticket 0058).

All four ``plot_companion_*.py`` scripts share:
- a preferred location for their input CSVs (``content/tables/``),
- a ``--tables-dir`` override used by the test suite,
- the companion config block in ``config/analysis.yaml``,
- a thin wrapper around ``pipeline_io.save_figure`` that respects
  ``os.path.splitext(--output)[0]`` as the stem (so Make controls the path).

Keeping this logic in one place avoids duplication across the four plot
scripts while staying well inside Phase 2 rules 4 (compute/plot/include
separate) and 5 (save_figure mandatory).
"""

import os
from typing import Any

import pandas as pd
from pipeline_io import save_figure
from utils import load_analysis_config

DEFAULT_TABLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "content",
    "tables",
)

# Method IDs in the fixed lead order used by the heatmap and Z-series panels.
DISTANCE_METHODS = ("S2_energy", "L1", "G9_community", "G2_spectral")
C2ST_CHANNELS = ("embedding", "lexical")


def companion_config() -> dict[str, Any]:
    """Return the ``companion`` block of ``config/analysis.yaml``.

    Raises
    ------
    KeyError if the block is missing — plot scripts should surface the
    config-discipline violation rather than silently fall back to defaults.

    """
    cfg = load_analysis_config()
    if "companion" not in cfg:
        raise KeyError(
            "config/analysis.yaml is missing the 'companion:' block. "
            "Add it per ticket 0058."
        )
    return cfg["companion"]


def add_tables_dir_arg(parser) -> None:
    """Register the shared ``--tables-dir`` option on an argparse parser."""
    parser.add_argument(
        "--tables-dir",
        default=DEFAULT_TABLES_DIR,
        help=(
            "Directory holding tab_summary_*.csv / tab_div_C2ST_*.csv / "
            "tab_discrim_terms*.csv / tab_community_shifts*.csv. "
            "Defaults to content/tables/."
        ),
    )


def read_csv_or_none(path: str) -> pd.DataFrame | None:
    """Return a DataFrame or ``None`` if the file is absent."""
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def load_summary_tables(tables_dir: str) -> dict[str, pd.DataFrame]:
    """Load tab_summary_{method}.csv for the four distance methods.

    Missing tables are skipped (the caller decides whether to degrade
    gracefully).  Returns a dict {method: DataFrame}.
    """
    out: dict[str, pd.DataFrame] = {}
    for method in DISTANCE_METHODS:
        df = read_csv_or_none(os.path.join(tables_dir, f"tab_summary_{method}.csv"))
        if df is not None and not df.empty:
            out[method] = df
    return out


def load_c2st_tables(tables_dir: str) -> dict[str, pd.DataFrame]:
    """Load tab_div_C2ST_{embedding,lexical}.csv.

    Returns a dict keyed ``'C2ST_embedding'`` / ``'C2ST_lexical'`` so the
    four distance keys and the two C2ST keys live in the same namespace.
    """
    out: dict[str, pd.DataFrame] = {}
    for channel in C2ST_CHANNELS:
        df = read_csv_or_none(os.path.join(tables_dir, f"tab_div_C2ST_{channel}.csv"))
        if df is not None and not df.empty:
            out[f"C2ST_{channel}"] = df
    return out


def save_companion_figure(fig, output_path: str, dpi: int = 300) -> None:
    """Strip the extension from ``output_path`` and save via ``save_figure``."""
    stem = os.path.splitext(output_path)[0]
    save_figure(fig, stem, dpi=dpi)


def window_rows(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Return rows whose ``window`` column matches ``window``.

    The CSVs use a string-or-int window; coerce defensively.
    """
    if "window" not in df.columns:
        return df
    w_str = str(window)
    mask = df["window"].astype(str).eq(w_str)
    return df.loc[mask]


def validated_zone_mask(
    z_frame: pd.DataFrame,
    z_threshold: float,
    min_methods: int,
) -> pd.Series:
    """Return a boolean Series (indexed by year) marking validated zones.

    ``z_frame`` is a year-indexed DataFrame whose columns are method IDs
    and whose values are signed signals.  A year is validated when at
    least ``min_methods`` columns have ``|signal| >= z_threshold``.
    """
    above = z_frame.abs().ge(z_threshold)
    return above.sum(axis=1) >= min_methods
