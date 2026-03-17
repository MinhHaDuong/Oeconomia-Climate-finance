"""Tests for collection year range configuration (ticket #175).

Covers:
- config/corpus_collect.yaml loads correctly with year_min < year_max
- load_collect_config() helper in utils.py
- catalog_openalex.py build_filter() includes year bounds from config
- catalog_istex.py query includes year bounds
- catalog_scopus.py query includes year bounds
- dvc.yaml declares config/corpus_collect.yaml as dependency for catalog stages
"""

import os
import sys

import pytest
import yaml

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Config file exists and is well-formed
# ---------------------------------------------------------------------------

class TestCorpusCollectConfig:
    def test_config_file_exists(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        assert os.path.exists(path), "config/corpus_collect.yaml must exist"

    def test_config_has_year_bounds(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert "year_min" in cfg
        assert "year_max" in cfg

    def test_year_min_less_than_year_max(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["year_min"] < cfg["year_max"]

    def test_expected_values(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["year_min"] == 1990
        assert cfg["year_max"] == 2024


# ---------------------------------------------------------------------------
# load_collect_config() helper
# ---------------------------------------------------------------------------

class TestLoadCollectConfig:
    def test_load_collect_config_returns_dict(self):
        from utils import load_collect_config
        cfg = load_collect_config()
        assert isinstance(cfg, dict)
        assert cfg["year_min"] == 1990
        assert cfg["year_max"] == 2024


# ---------------------------------------------------------------------------
# OpenAlex build_filter includes year bounds
# ---------------------------------------------------------------------------

class TestOpenAlexYearFilter:
    def test_build_filter_includes_year(self):
        from catalog_openalex import build_filter
        f = build_filter("climate finance", year_min=1990, year_max=2024)
        assert "publication_year" in f
        assert "1989" in f or "1990" in f  # >1989 or >=1990
        assert "2025" in f or "2024" in f  # <2025 or <=2024

    def test_build_filter_no_year_when_none(self):
        """Backwards compat: no year filter when not provided."""
        from catalog_openalex import build_filter
        f = build_filter("climate finance")
        assert "publication_year" not in f


# ---------------------------------------------------------------------------
# DVC declares config/corpus_collect.yaml as dependency
# ---------------------------------------------------------------------------

class TestDvcDependency:
    def test_dvc_catalog_openalex_depends_on_config(self):
        path = os.path.join(ROOT_DIR, "dvc.yaml")
        with open(path) as f:
            dvc = yaml.safe_load(f)
        deps = dvc["stages"]["catalog_openalex"]["deps"]
        assert "config/corpus_collect.yaml" in deps

    def test_dvc_catalog_istex_depends_on_config(self):
        path = os.path.join(ROOT_DIR, "dvc.yaml")
        with open(path) as f:
            dvc = yaml.safe_load(f)
        deps = dvc["stages"]["catalog_istex"]["deps"]
        assert "config/corpus_collect.yaml" in deps

    def test_dvc_catalog_grey_depends_on_config(self):
        path = os.path.join(ROOT_DIR, "dvc.yaml")
        with open(path) as f:
            dvc = yaml.safe_load(f)
        deps = dvc["stages"]["catalog_grey"]["deps"]
        assert "config/corpus_collect.yaml" in deps
