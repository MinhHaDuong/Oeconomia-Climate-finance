"""Smoke tests for the four companion-paper figure scripts (ticket 0058).

Each of the four scripts:
- ``scripts/plot_companion_zseries.py``    — Figure 1 (Z-score time series)
- ``scripts/plot_companion_heatmap.py``    — Figure 2 (transition zone heatmap)
- ``scripts/plot_companion_terms.py``      — Figure 3 (discriminative terms)
- ``scripts/plot_companion_community.py``  — Figure 4 (community flow)

must

1. exist on disk,
2. accept ``--output <path>`` via the shared ``parse_io_args`` parser,
3. produce a non-empty PNG when invoked on synthetic fixture data.

Tests use small synthetic CSVs matching the pipeline schemas so the suite
does not depend on the real ``tab_summary_*.csv`` / ``tab_div_C2ST_*.csv``
outputs being present on disk.
"""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = REPO / "scripts"

COMPANION_SCRIPTS = {
    "zseries": "plot_companion_zseries.py",
    "heatmap": "plot_companion_heatmap.py",
    "terms": "plot_companion_terms.py",
    "community": "plot_companion_community.py",
}


# ─── Fixture data ────────────────────────────────────────────────────────


def _summary_fixture(method: str) -> pd.DataFrame:
    """Synthetic tab_summary_{method}.csv matching the pipeline schema."""
    rows = []
    for year in range(1998, 2022):
        for window in (2, 3, 4, 5):
            # Produce a mild bump around 2009 so the plots are not flat.
            z = 2.5 if year in (2008, 2009, 2010) else 0.4
            rows.append(
                {
                    "method": method,
                    "year": year,
                    "window": window,
                    "hyperparams": "default",
                    "point_estimate": 0.05 + 0.001 * (year - 2000),
                    "boot_median": 0.07,
                    "boot_q025": 0.05,
                    "boot_q975": 0.09,
                    "z_score": z,
                    "p_value": 0.01 if z > 2 else 0.3,
                    "significant": bool(z > 2),
                }
            )
    return pd.DataFrame(rows)


def _c2st_fixture(channel: str) -> pd.DataFrame:
    rows = []
    for year in range(1998, 2022):
        for window in (2, 3, 4, 5):
            auc = 0.82 if year in (2008, 2009, 2010) else 0.55
            rows.append(
                {
                    "year": year,
                    "window": window,
                    "hyperparams": "pca=32",
                    "value": auc,
                    "auc_std": 0.05,
                    "auc_q025": auc - 0.07,
                    "auc_q975": auc + 0.07,
                    "n_folds": 5,
                    "p_value_vs_chance": 0.001 if auc > 0.7 else 0.2,
                    "channel": channel,
                }
            )
    return pd.DataFrame(rows)


def _terms_fixture() -> pd.DataFrame:
    """Synthetic discriminative-terms table (one zone, ten terms)."""
    terms = [f"term_{i}" for i in range(10)]
    rows = []
    for zone in ("2008-2010", "2014-2016"):
        for t in terms:
            rows.append(
                {
                    "zone": zone,
                    "term": t,
                    "log_odds": 0.5 if zone.startswith("2008") else -0.4,
                    "direction": "after" if zone.startswith("2008") else "before",
                    "rank": terms.index(t) + 1,
                }
            )
    return pd.DataFrame(rows)


def _community_fixture() -> pd.DataFrame:
    """Synthetic community shifts table for zones."""
    rows = []
    for zone in ("2008-2010", "2014-2016"):
        for side in ("before", "after"):
            for cid in range(3):
                rows.append(
                    {
                        "zone": zone,
                        "side": side,
                        "community_id": cid,
                        "size": 50 + 10 * cid + (5 if side == "after" else 0),
                        "label": f"c{cid}",
                    }
                )
    return pd.DataFrame(rows)


@pytest.fixture
def companion_tables(tmp_path: Path) -> Path:
    """Write fixture CSVs into ``tmp_path/tables`` and return that directory."""
    tables = tmp_path / "tables"
    tables.mkdir()
    for m in ("S2_energy", "L1", "G9_community", "G2_spectral"):
        _summary_fixture(m).to_csv(tables / f"tab_summary_{m}.csv", index=False)
    _c2st_fixture("semantic").to_csv(tables / "tab_div_C2ST_embedding.csv", index=False)
    _c2st_fixture("lexical").to_csv(tables / "tab_div_C2ST_lexical.csv", index=False)
    _terms_fixture().to_csv(tables / "tab_discrim_terms.csv", index=False)
    _community_fixture().to_csv(tables / "tab_community_shifts.csv", index=False)
    return tables


# ─── Helpers ─────────────────────────────────────────────────────────────


def _run(script: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_png(path: Path) -> None:
    assert path.exists(), f"expected PNG at {path}"
    assert path.stat().st_size > 1000, (
        f"PNG at {path} is suspiciously small ({path.stat().st_size} bytes)"
    )


# ─── Existence & CLI contract ────────────────────────────────────────────


@pytest.mark.parametrize("script", list(COMPANION_SCRIPTS.values()))
def test_script_exists(script: str):
    assert (SCRIPTS_DIR / script).is_file(), f"{script} missing"


@pytest.mark.parametrize("script", list(COMPANION_SCRIPTS.values()))
def test_script_requires_output(script: str):
    """Running without --output must fail with a non-zero exit."""
    proc = _run(script, [])
    assert proc.returncode != 0, (
        f"{script} should require --output; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


# ─── End-to-end smoke (fixture data → non-empty PNG) ─────────────────────


def test_zseries_runs(tmp_path: Path, companion_tables: Path):
    out = tmp_path / "fig_companion_zseries.png"
    proc = _run(
        COMPANION_SCRIPTS["zseries"],
        [
            "--output",
            str(out),
            "--tables-dir",
            str(companion_tables),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    _assert_png(out)


def test_heatmap_runs(tmp_path: Path, companion_tables: Path):
    out = tmp_path / "fig_companion_heatmap.png"
    proc = _run(
        COMPANION_SCRIPTS["heatmap"],
        [
            "--output",
            str(out),
            "--tables-dir",
            str(companion_tables),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    _assert_png(out)


def test_terms_runs(tmp_path: Path, companion_tables: Path):
    out = tmp_path / "fig_companion_terms.png"
    proc = _run(
        COMPANION_SCRIPTS["terms"],
        [
            "--output",
            str(out),
            "--tables-dir",
            str(companion_tables),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    _assert_png(out)


def test_community_runs(tmp_path: Path, companion_tables: Path):
    out = tmp_path / "fig_companion_community.png"
    proc = _run(
        COMPANION_SCRIPTS["community"],
        [
            "--output",
            str(out),
            "--tables-dir",
            str(companion_tables),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    _assert_png(out)
