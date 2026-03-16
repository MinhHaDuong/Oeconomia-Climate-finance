"""Tests for the teaching source pipeline.

Verifies that:
- build_teaching_yaml.py converts CSV → YAML correctly
- build_teaching_canon.py reads from data/ (not config/)
- dvc.yaml references the right paths
"""

import os
import sys
import tempfile

import pandas as pd
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")


class TestBuildTeachingYaml:
    """Tests for build_teaching_yaml.py."""

    def _make_csv(self, tmp_path, rows):
        """Create a minimal reading_lists.csv."""
        cols = ["doi", "title", "authors", "year", "journal_or_publisher",
                "type", "courses", "institutions", "countries", "n_courses",
                "in_corpus"]
        df = pd.DataFrame(rows, columns=cols)
        csv_path = os.path.join(tmp_path, "reading_lists.csv")
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_csv_to_yaml_roundtrip(self, tmp_path):
        """CSV readings are converted to YAML with correct schema."""
        from build_teaching_yaml import load_and_explode, build_yaml_structure

        rows = [
            {"doi": "10.1234/test1", "title": "Test Paper",
             "authors": "Smith, Jones", "year": 2023, "journal_or_publisher": "",
             "type": "article", "courses": "Climate Finance 101 ; Advanced CF",
             "institutions": "Test University ; Uni C", "countries": "France",
             "n_courses": 2, "in_corpus": True},
            {"doi": "10.1234/test2", "title": "Climate Paper",
             "authors": "Doe", "year": 2020, "journal_or_publisher": "Publisher",
             "type": "article", "courses": "Green Finance ; Sustainable Investing",
             "institutions": "Uni A ; Uni B", "countries": "France ; Germany",
             "n_courses": 2, "in_corpus": False},
        ]
        csv_path = self._make_csv(str(tmp_path), rows)

        records = load_and_explode(csv_path)
        # 2 records for row 0, 2 records for row 1 (exploded)
        assert len(records) == 4

        sources = build_yaml_structure(records)
        assert len(sources) == 4  # 4 unique (institution, course) pairs

        # Verify YAML schema
        for src in sources:
            assert "institution" in src
            assert "course" in src
            assert "level" in src
            assert "region" in src
            assert "readings" in src
            for r in src["readings"]:
                assert "doi" in r or "title" in r

    def test_doi_dedup_within_course(self, tmp_path):
        """Duplicate DOIs within same course are deduplicated."""
        from build_teaching_yaml import load_and_explode, build_yaml_structure

        rows = [
            {"doi": "10.1234/dup", "title": "Paper A", "authors": "",
             "year": 2023, "journal_or_publisher": "", "type": "article",
             "courses": "Course X ; Course Y", "institutions": "Uni X ; Uni Y",
             "countries": "", "n_courses": 2, "in_corpus": False},
            {"doi": "10.1234/dup", "title": "Paper A variant", "authors": "",
             "year": 2023, "journal_or_publisher": "", "type": "article",
             "courses": "Course X ; Course Y", "institutions": "Uni X ; Uni Y",
             "countries": "", "n_courses": 2, "in_corpus": False},
        ]
        csv_path = self._make_csv(str(tmp_path), rows)

        records = load_and_explode(csv_path)
        sources = build_yaml_structure(records)
        # 2 courses (Course X, Course Y), each with 1 reading (deduplicated)
        assert len(sources) == 2
        for s in sources:
            assert len(s["readings"]) == 1  # deduplicated within each course

    def test_region_inference(self):
        """Country strings map to correct regions."""
        from build_teaching_yaml import _infer_region

        assert _infer_region("France") == "Europe"
        assert _infer_region("USA") == "North America"
        assert _infer_region("Brazil") == "Latin America"
        assert _infer_region("Japan") == "Asia"
        assert _infer_region("") == "Global"
        assert _infer_region(None) == "Global"
        assert _infer_region("France ; USA") == "Global"  # mixed

    def test_level_inference(self):
        """Course names map to correct levels."""
        from build_teaching_yaml import _infer_level

        assert _infer_level("MBA Climate Finance") == "mba"
        assert _infer_level("Doctoral Seminar on Climate") == "doctoral"
        assert _infer_level("MOOC: Sustainable Finance") == "mooc"
        assert _infer_level("Master in Green Finance") == "masters"
        assert _infer_level("Professional Certificate") == "other"


class TestBuildTeachingCanonPath:
    """Verify build_teaching_canon.py reads from data/, not config/."""

    def test_yaml_path_is_data_dir(self):
        """YAML_PATH should reference data/, not config/."""
        from build_teaching_canon import YAML_PATH
        assert "data" in YAML_PATH
        assert "config" not in YAML_PATH


class TestDvcYamlIntegration:
    """Verify dvc.yaml references the correct paths."""

    def test_discover_stage_deps_include_syllabi(self):
        """The discover stage should depend on data/syllabi, not config/teaching_sources.yaml."""
        dvc_path = os.path.join(BASE_DIR, "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)

        discover = dvc["stages"]["discover"]
        deps = discover["deps"]

        assert "data/syllabi" in deps, "discover should depend on data/syllabi"
        assert "config/teaching_sources.yaml" not in deps, \
            "discover should NOT depend on config/teaching_sources.yaml"
        assert "scripts/build_teaching_yaml.py" in deps, \
            "discover should depend on build_teaching_yaml.py"

    def test_discover_stage_runs_build_teaching_yaml(self):
        """The discover stage command should run build_teaching_yaml.py before build_teaching_canon.py."""
        dvc_path = os.path.join(BASE_DIR, "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)

        cmd = dvc["stages"]["discover"]["cmd"]
        assert "build_teaching_yaml.py" in cmd
        assert "build_teaching_canon.py" in cmd
        # yaml must come before canon
        assert cmd.index("build_teaching_yaml.py") < cmd.index("build_teaching_canon.py")
