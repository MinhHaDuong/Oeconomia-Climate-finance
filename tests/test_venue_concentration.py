"""Tests for venue concentration (Herfindahl / Shannon entropy) per year.

Ticket 0073: bias B4 (editorial cartel / venue concentration).

Tests:
1. Unit test: compute_concentration on synthetic data — verifies columns, HHI range,
   and known HHI/entropy values computed by hand.
2. Integration test: run script via subprocess, validate output CSV schema.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


class TestComputeConcentration:
    """Unit tests for the compute_concentration function."""

    def test_hhi_columns(self):
        """Output has expected columns and HHI in [0, 1]."""
        from compute_venue_concentration import compute_concentration

        df = pd.DataFrame(
            {
                "year": [2010, 2010, 2010, 2010, 2011],
                "journal": [
                    "Nature Climate Change",
                    "Nature Climate Change",
                    "Nature Climate Change",
                    "Energy Policy",
                    "Climatic Change",
                ],
            }
        )
        result = compute_concentration(df)
        assert set(result.columns) == {
            "year",
            "hhi",
            "shannon_entropy",
            "n_venues",
            "n_papers",
        }
        assert (result["hhi"] >= 0).all()
        assert (result["hhi"] <= 1).all()

    def test_known_values(self):
        """Verify HHI and entropy against hand-computed values.

        Year 2010: venues A (3 papers), B (1 paper)
          shares = [0.75, 0.25]
          HHI = 0.75^2 + 0.25^2 = 0.625
          Entropy = -(0.75*ln(0.75) + 0.25*ln(0.25)) ≈ 0.5623

        Year 2011: venue C (1 paper)
          HHI = 1.0
          Entropy = 0.0
        """
        from compute_venue_concentration import compute_concentration

        df = pd.DataFrame(
            {
                "year": [2010, 2010, 2010, 2010, 2011],
                "journal": ["A", "A", "A", "B", "C"],
            }
        )
        result = compute_concentration(df)
        result = result.sort_values("year").reset_index(drop=True)

        # Year 2010
        row_2010 = result[result["year"] == 2010].iloc[0]
        assert row_2010["n_venues"] == 2
        assert row_2010["n_papers"] == 4
        assert abs(row_2010["hhi"] - 0.625) < 1e-6
        expected_entropy = -(0.75 * np.log(0.75) + 0.25 * np.log(0.25))
        assert abs(row_2010["shannon_entropy"] - expected_entropy) < 1e-6

        # Year 2011 — single venue
        row_2011 = result[result["year"] == 2011].iloc[0]
        assert row_2011["n_venues"] == 1
        assert row_2011["n_papers"] == 1
        assert row_2011["hhi"] == 1.0
        assert row_2011["shannon_entropy"] == 0.0

    def test_excludes_non_journal_venues(self):
        """Non-journal venues (working papers, repositories) are excluded."""
        from compute_venue_concentration import compute_concentration

        df = pd.DataFrame(
            {
                "year": [2010, 2010, 2010],
                "journal": [
                    "Nature Climate Change",
                    "SSRN Electronic Journal",
                    "World Bank Policy Research Working Paper",
                ],
            }
        )
        result = compute_concentration(df)
        row = result.iloc[0]
        # Only Nature Climate Change should remain (SSRN = repository, WB = working paper)
        assert row["n_venues"] == 1
        assert row["n_papers"] == 1
        assert row["hhi"] == 1.0

    def test_excludes_null_journals(self):
        """Null/empty journal values are excluded."""
        from compute_venue_concentration import compute_concentration

        df = pd.DataFrame(
            {
                "year": [2010, 2010, 2010],
                "journal": ["Nature Climate Change", "", None],
            }
        )
        result = compute_concentration(df)
        assert result.iloc[0]["n_papers"] == 1

    def test_schema_validation(self):
        """Output passes VenueConcentrationSchema."""
        from compute_venue_concentration import compute_concentration
        from schemas import VenueConcentrationSchema

        df = pd.DataFrame(
            {
                "year": [2010, 2010, 2011],
                "journal": ["A", "B", "A"],
            }
        )
        result = compute_concentration(df)
        VenueConcentrationSchema.validate(result)


@pytest.mark.integration
class TestVenueConcentrationSubprocess:
    """Integration test: run the compute script via subprocess."""

    def test_runs_and_produces_output(self, tmp_path):
        import subprocess

        # Create a minimal refined_works-like CSV
        df = pd.DataFrame(
            {
                "source": ["openalex"] * 5,
                "source_id": [f"id_{i}" for i in range(5)],
                "doi": [f"10.1234/{i}" for i in range(5)],
                "title": [f"Paper {i}" for i in range(5)],
                "first_author": ["Author"] * 5,
                "all_authors": ["Author"] * 5,
                "year": ["2010", "2010", "2010", "2011", "2011"],
                "journal": [
                    "Nature Climate Change",
                    "Nature Climate Change",
                    "Energy Policy",
                    "Energy Policy",
                    "Climatic Change",
                ],
                "abstract": ["text"] * 5,
                "language": ["en"] * 5,
                "keywords": [""] * 5,
                "categories": [""] * 5,
                "cited_by_count": ["10"] * 5,
                "affiliations": [""] * 5,
                "from_openalex": ["1"] * 5,
                "from_istex": ["0"] * 5,
                "from_bibcnrs": ["0"] * 5,
                "from_scispace": ["0"] * 5,
                "from_grey": ["0"] * 5,
                "from_teaching": ["0"] * 5,
                "source_count": ["1"] * 5,
                "abstract_status": ["ok"] * 5,
                "near_duplicate_group": [""] * 5,
                "in_v1": ["1"] * 5,
            }
        )
        input_csv = tmp_path / "refined_works.csv"
        df.to_csv(input_csv, index=False)

        output_csv = tmp_path / "tab_venue_concentration.csv"
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                os.path.join(SCRIPTS_DIR, "compute_venue_concentration.py"),
                "--output",
                str(output_csv),
                "--input",
                str(input_csv),
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"
        assert output_csv.exists()

        out_df = pd.read_csv(output_csv)
        assert set(out_df.columns) == {
            "year",
            "hhi",
            "shannon_entropy",
            "n_venues",
            "n_papers",
        }
        assert (out_df["hhi"] >= 0).all()
        assert (out_df["hhi"] <= 1).all()
