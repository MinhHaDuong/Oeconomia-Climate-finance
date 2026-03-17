"""Tests for centralized analysis year range in config/analysis.yaml.

Verifies that:
- Config has year_min/year_max in periodization section
- load_analysis_periods() derives correct period tuples and labels
- Warning fires when analysis range exceeds collection range
"""

import os
import sys
import warnings

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from utils import load_analysis_config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestAnalysisYamlStructure:
    """Config has year_min < breaks[0] < breaks[-1] < year_max."""

    def test_periodization_has_year_min(self):
        cfg = load_analysis_config()
        assert "year_min" in cfg["periodization"], (
            "analysis.yaml periodization section must have year_min"
        )

    def test_periodization_has_year_max(self):
        cfg = load_analysis_config()
        assert "year_max" in cfg["periodization"], (
            "analysis.yaml periodization section must have year_max"
        )

    def test_year_min_before_first_break(self):
        cfg = load_analysis_config()
        p = cfg["periodization"]
        assert p["year_min"] < p["breaks"][0], (
            f"year_min ({p['year_min']}) must be before first break ({p['breaks'][0]})"
        )

    def test_year_max_after_last_break(self):
        cfg = load_analysis_config()
        p = cfg["periodization"]
        assert p["year_max"] > p["breaks"][-1], (
            f"year_max ({p['year_max']}) must be after last break ({p['breaks'][-1]})"
        )

    def test_year_min_is_1990(self):
        cfg = load_analysis_config()
        assert cfg["periodization"]["year_min"] == 1990

    def test_year_max_is_2024(self):
        cfg = load_analysis_config()
        assert cfg["periodization"]["year_max"] == 2024


class TestLoadAnalysisPeriods:
    """load_analysis_periods() returns correct tuples and labels."""

    def test_returns_periods_and_labels(self):
        from utils import load_analysis_periods
        periods, labels = load_analysis_periods()
        assert isinstance(periods, list)
        assert isinstance(labels, list)

    def test_period_tuples(self):
        from utils import load_analysis_periods
        periods, _ = load_analysis_periods()
        assert periods == [(1990, 2006), (2007, 2014), (2015, 2024)]

    def test_period_labels(self):
        from utils import load_analysis_periods
        _, labels = load_analysis_periods()
        assert labels == ["1990\u20132006", "2007\u20132014", "2015\u20132024"]

    def test_period_count_matches_labels(self):
        from utils import load_analysis_periods
        periods, labels = load_analysis_periods()
        assert len(periods) == len(labels)

    def test_periods_dict(self):
        """Convenience: labels map to tuples."""
        from utils import load_analysis_periods
        periods, labels = load_analysis_periods()
        d = dict(zip(labels, periods))
        assert d["2015\u20132024"] == (2015, 2024)


class TestCollectionRangeWarning:
    """Warning fires when analysis range exceeds collection range."""

    def test_warns_when_analysis_exceeds_collection(self, tmp_path):
        """Create fake configs where analysis range exceeds collection range."""
        from utils import load_analysis_periods

        # Create a temporary analysis.yaml with range wider than collection
        analysis_cfg = {
            "periodization": {
                "year_min": 1980,
                "year_max": 2030,
                "breaks": [2007, 2015],
            },
            "clustering": {"k": 6, "cite_threshold": 50},
        }
        collect_cfg = {
            "year_min": 1990,
            "year_max": 2024,
        }

        analysis_path = tmp_path / "analysis.yaml"
        collect_path = tmp_path / "corpus_collect.yaml"
        with open(analysis_path, "w") as f:
            yaml.dump(analysis_cfg, f)
        with open(collect_path, "w") as f:
            yaml.dump(collect_cfg, f)

        with pytest.warns(UserWarning, match="exceeds collection range"):
            load_analysis_periods(config_dir=str(tmp_path))

    def test_no_warning_when_within_range(self, tmp_path):
        """No warning when analysis range is within collection range."""
        from utils import load_analysis_periods

        analysis_cfg = {
            "periodization": {
                "year_min": 1990,
                "year_max": 2024,
                "breaks": [2007, 2015],
            },
            "clustering": {"k": 6, "cite_threshold": 50},
        }
        collect_cfg = {
            "year_min": 1985,
            "year_max": 2025,
        }

        analysis_path = tmp_path / "analysis.yaml"
        collect_path = tmp_path / "corpus_collect.yaml"
        with open(analysis_path, "w") as f:
            yaml.dump(analysis_cfg, f)
        with open(collect_path, "w") as f:
            yaml.dump(collect_cfg, f)

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # Should not raise any warnings
            load_analysis_periods(config_dir=str(tmp_path))

    def test_no_warning_when_collect_missing(self):
        """No warning/error when corpus_collect.yaml doesn't exist yet."""
        from utils import load_analysis_periods

        # Default config_dir; corpus_collect.yaml doesn't exist
        # Should succeed without warning
        periods, labels = load_analysis_periods()
        assert len(periods) == 3
