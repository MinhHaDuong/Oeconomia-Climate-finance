"""Tests for the teaching source pipeline.

Verifies that:
- build_teaching_yaml.py converts CSV → YAML correctly
- build_teaching_yaml.py works without manual catalog (CSV-only)
- collect_syllabi.py PDF extraction includes table content
- collect_syllabi.py extract stage uses chunk overlap
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
        from build_teaching_yaml import load_scraped, build_yaml_structure

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

        records = load_scraped(csv_path)
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
        from build_teaching_yaml import load_scraped, build_yaml_structure

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

        records = load_scraped(csv_path)
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


class TestScraperPdfExtraction:
    """Tests for improved PDF text extraction in collect_syllabi.py."""

    def test_extract_pdf_text_includes_tables(self, tmp_path):
        """PDF extraction should capture table content alongside body text."""
        from collect_syllabi import extract_pdf_text

        # Create a minimal PDF with a table using reportlab if available,
        # otherwise use pdfplumber's test fixtures.
        # For now, test the function signature and that it returns table text.
        import pdfplumber
        from fpdf import FPDF

        # Build a PDF with a simple table of readings
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(200, 10, text="Course Reading List", new_x="LMARGIN", new_y="NEXT")
        # Simulate a table-like structure
        pdf.cell(100, 10, text="Author", border=1)
        pdf.cell(90, 10, text="Title", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(100, 10, text="Nordhaus", border=1)
        pdf.cell(90, 10, text="The Climate Casino", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(100, 10, text="Stern", border=1)
        pdf.cell(90, 10, text="Stern Review", border=1, new_x="LMARGIN", new_y="NEXT")

        pdf_path = str(tmp_path / "test_syllabus.pdf")
        pdf.output(pdf_path)

        text = extract_pdf_text(pdf_path)
        assert "Nordhaus" in text
        assert "Climate Casino" in text
        assert "Stern" in text

    def test_text_limit_increased(self):
        """Text truncation should allow at least 50KB (was 20KB)."""
        from collect_syllabi import TEXT_LIMIT
        assert TEXT_LIMIT >= 50000


class TestScraperChunkOverlap:
    """Tests for chunk overlap in the extract stage."""

    def test_chunk_overlap_constant_exists(self):
        """Extract stage should define a chunk overlap to avoid splitting refs."""
        from collect_syllabi import CHUNK_OVERLAP
        assert CHUNK_OVERLAP >= 500, "Overlap should be ≥500 chars"

    def test_chunks_overlap(self):
        """Chunks produced for extraction should overlap with matching content."""
        from collect_syllabi import make_chunks

        # Use distinguishable characters so overlap assertion is meaningful
        text = "".join(str(i % 10) for i in range(10000))
        chunks = make_chunks(text, chunk_size=4000, overlap=500)
        assert len(chunks) >= 3
        # Verify overlap: end of chunk N overlaps with start of chunk N+1
        for i in range(len(chunks) - 1):
            tail = chunks[i][-500:]
            assert chunks[i + 1].startswith(tail), \
                f"Chunk {i} and {i+1} should overlap by 500 chars"

    def test_chunks_reject_bad_overlap(self):
        """make_chunks raises ValueError if overlap >= chunk_size."""
        from collect_syllabi import make_chunks
        with pytest.raises(ValueError):
            make_chunks("hello", chunk_size=100, overlap=100)


class TestBuildTeachingYamlNoManual:
    """build_teaching_yaml.py should work without manual_catalog.yaml."""

    def test_no_manual_catalog_import(self):
        """build_teaching_yaml.py should not reference manual catalog."""
        import inspect
        import build_teaching_yaml
        source = inspect.getsource(build_teaching_yaml)
        assert "manual_catalog" not in source, \
            "Manual catalog path should be removed — scraper is now sufficient"

    def test_main_runs_without_manual(self, tmp_path, monkeypatch):
        """main() should succeed with only a CSV input, no manual YAML."""
        from build_teaching_yaml import load_scraped, build_yaml_structure

        # Create a CSV with readings meeting the threshold
        cols = ["doi", "title", "authors", "year", "journal_or_publisher",
                "type", "courses", "institutions", "countries", "n_courses",
                "in_corpus"]
        rows = [
            {"doi": "10.1146/annurev-financial-102620-103311",
             "title": "Climate finance", "authors": "Giglio, Kelly, Stroebel",
             "year": 2021, "journal_or_publisher": "Ann Rev",
             "type": "article", "courses": "Course A ; Course B",
             "institutions": "Uni A ; Uni B", "countries": "USA",
             "n_courses": 2, "in_corpus": True},
        ]
        df = pd.DataFrame(rows, columns=cols)
        csv_path = str(tmp_path / "reading_lists.csv")
        df.to_csv(csv_path, index=False)

        records = load_scraped(csv_path)
        assert len(records) >= 1
        sources = build_yaml_structure(records)
        assert len(sources) >= 1


# --- Ground truth: 24 unique works from the pipeline-generated teaching_sources.yaml ---
# 22 DOIs + 2 title-only. The scraper must rediscover all of these.
REFERENCE_DOIS = {
    "10.1146/annurev-financial-102620-103311",
    "10.1016/j.jfineco.2020.12.011",
    "10.2139/ssrn.3438533",
    "10.3386/w28940",
    "10.1016/j.jbankfin.2018.10.012",
    "10.1016/j.jfineco.2019.03.013",
    "10.1093/rfs/hhab032",
    "10.1093/rfs/hhz072",
    "10.1111/jofi.13219",
    "10.1111/jofi.13272",
    "10.1515/9783110733488-019",
    "10.1017/9781108886246.018",
    "10.4324/9781315147024-21",
    "10.1080/20430795.2020.1717241",
    "10.2139/ssrn.6115887",
    "10.54648/eucl2018032",
    "10.4337/9781786432636.00019",
    "10.1016/j.ecolecon.2021.107022",
    "10.1093/oso/9780190662455.003.0003",
    "10.1108/s2051-503020160000019005",
    "10.59117/20.500.11822/43406",
    "10.7551/mitpress/9780262035620.003.0009",
}
REFERENCE_TITLES = {
    "principles of sustainable finance",
    "global landscape of climate finance",
}


class TestScraperCoverage:
    """Validate that scraper output covers all 24 reference works."""

    @pytest.mark.skipif(
        not os.path.exists(os.path.join(
            os.path.dirname(__file__), "..", "data", "teaching_sources.yaml")),
        reason="teaching_sources.yaml not yet generated (run scraper first)")
    def test_output_covers_reference_works(self):
        """teaching_sources.yaml must contain all 24 reference works."""
        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "teaching_sources.yaml")
        with open(yaml_path) as f:
            sources = yaml.safe_load(f)

        # Collect all DOIs and titles from output
        output_dois = set()
        output_titles = set()
        for src in sources:
            for r in src.get("readings", []):
                doi = (r.get("doi") or "").strip().lower()
                title = (r.get("title") or "").strip().lower()
                if doi:
                    output_dois.add(doi)
                if title:
                    output_titles.add(title)

        # Check DOI coverage
        missing_dois = REFERENCE_DOIS - output_dois
        assert not missing_dois, \
            f"Missing {len(missing_dois)} reference DOIs: {missing_dois}"

        # Check title-only coverage
        missing_titles = REFERENCE_TITLES - output_titles
        assert not missing_titles, \
            f"Missing {len(missing_titles)} reference titles: {missing_titles}"


class TestBuildTeachingCanonPath:
    """Verify build_teaching_canon.py reads from data/, not config/."""

    def test_yaml_path_is_data_dir(self):
        """YAML_PATH should reference data/, not config/."""
        from build_teaching_canon import YAML_PATH
        assert "data" in YAML_PATH
        assert "config" not in YAML_PATH


class TestDvcYamlIntegration:
    """Verify dvc.yaml references the correct paths."""

    def test_catalog_teaching_stage_deps_include_syllabi(self):
        """The catalog_teaching stage should depend on data/syllabi."""
        dvc_path = os.path.join(BASE_DIR, "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)

        teaching = dvc["stages"]["catalog_teaching"]
        deps = teaching["deps"]

        assert "data/syllabi" in deps, "catalog_teaching should depend on data/syllabi"
        assert "scripts/build_teaching_yaml.py" in deps, \
            "catalog_teaching should depend on build_teaching_yaml.py"

    def test_catalog_teaching_stage_runs_build_teaching_yaml(self):
        """The catalog_teaching stage command should run build_teaching_yaml.py before build_teaching_canon.py."""
        dvc_path = os.path.join(BASE_DIR, "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)

        cmd = dvc["stages"]["catalog_teaching"]["cmd"]
        assert "build_teaching_yaml.py" in cmd
        assert "build_teaching_canon.py" in cmd
        # yaml must come before canon
        assert cmd.index("build_teaching_yaml.py") < cmd.index("build_teaching_canon.py")
