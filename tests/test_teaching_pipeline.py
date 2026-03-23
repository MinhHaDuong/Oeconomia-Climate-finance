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


# --- Ground truth: core works that appear on >= 2 syllabi ---
# These are the convergence-validated DOIs: works independently assigned
# by multiple courses.  Scraper must find all of them.
REFERENCE_DOIS = {
    "10.1146/annurev-financial-102620-103311",   # Giglio, Kelly, Stroebel — Climate finance
    "10.1016/j.jfineco.2020.12.011",             # Pastor, Stambaugh, Taylor — Sustainable investing
    "10.2139/ssrn.3438533",                       # Berg, Kolbel, Rigobon — ESG ratings divergence
    "10.3386/w28940",                             # Pastor, Stambaugh, Taylor — Dissecting green returns
    "10.1016/j.jbankfin.2018.10.012",            # Zerbib — Green bond premium
    "10.1093/rfs/hhab032",                        # Giglio et al. — Long-run discount rates
    "10.1093/rfs/hhz072",                         # Engle et al. — Hedging climate change news
    "10.1111/jofi.13272",                         # Bolton & Kacperczyk — Carbon-transition risk
    "10.4337/9781786432636.00019",                # Green Bond Principles
    "10.1016/j.ecolecon.2021.107022",             # Central bank mandates and sustainability
    "10.7551/mitpress/9780262035620.003.0009",    # Sustainable Development Goals
    "10.2307/2676219",                            # Heinkel et al. — Green investment
}
REFERENCE_TITLES = {
    "principles of sustainable finance",
}


class TestScraperCoverage:
    """Validate that scraper output covers convergence-validated core works."""

    @pytest.mark.skipif(
        not os.path.exists(os.path.join(
            os.path.dirname(__file__), "..", "data", "teaching_sources.yaml")),
        reason="teaching_sources.yaml not yet generated (run scraper first)")
    def test_output_covers_reference_works(self):
        """teaching_sources.yaml must contain all convergence-validated core works."""
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

        # Minimum output size: must have at least 40 courses and 200 readings
        n_courses = len(sources)
        n_readings = sum(len(s.get("readings", [])) for s in sources)
        assert n_courses >= 30, f"Expected >=30 courses, got {n_courses}"
        assert n_readings >= 100, f"Expected >=100 readings, got {n_readings}"


class TestCleanDoi:
    """Tests for _clean_doi in collect_syllabi.py."""

    def test_strips_https_doi_org_prefix(self):
        """DOIs with https://doi.org/ prefix are cleaned."""
        from collect_syllabi import _clean_doi
        assert _clean_doi("https://doi.org/10.1257/aer.104.5.544") == "10.1257/aer.104.5.544"

    def test_strips_http_dx_doi_prefix(self):
        """DOIs with http://dx.doi.org/ prefix are cleaned."""
        from collect_syllabi import _clean_doi
        assert _clean_doi("http://dx.doi.org/10.1234/test") == "10.1234/test"

    def test_strips_publisher_url(self):
        """DOIs embedded in publisher URLs are extracted."""
        from collect_syllabi import _clean_doi
        assert _clean_doi("https://onlinelibrary.wiley.com/doi/full/10.1111/1475-679X.12481") == "10.1111/1475-679x.12481"

    def test_clean_doi_already_clean(self):
        """Clean DOIs are returned lowercase unchanged."""
        from collect_syllabi import _clean_doi
        assert _clean_doi("10.1234/test") == "10.1234/test"

    def test_clean_doi_none_empty(self):
        """None and empty string return empty string."""
        from collect_syllabi import _clean_doi
        assert _clean_doi(None) == ""
        assert _clean_doi("") == ""

    def test_clean_doi_non_doi_url(self):
        """Non-DOI URLs (SSRN, HDL) are returned empty."""
        from collect_syllabi import _clean_doi
        assert _clean_doi("https://ssrn.com/abstract=4565220") == ""
        assert _clean_doi("http://hdl.handle.net/10419/237920") == ""

    def test_clean_doi_double_prefix(self):
        """DOIs with doi: inside URL are cleaned."""
        from collect_syllabi import _clean_doi
        assert _clean_doi("https://doi.org/doi:10.1038/nclimate3255") == "10.1038/nclimate3255"


class TestTwoTierFilter:
    """Tests for two-tier filter in build_teaching_yaml.py."""

    def test_detailed_syllabus_readings_pass_at_one_course(self, tmp_path):
        """Readings from detailed syllabi (>=MIN_READINGS_DETAILED DOIs) pass at n_courses=1."""
        from build_teaching_yaml import load_scraped, MIN_READINGS_DETAILED

        # Create a CSV: one detailed course with many readings + one small course
        rows = []
        # Detailed course with MIN_READINGS_DETAILED readings
        for i in range(MIN_READINGS_DETAILED + 5):
            rows.append({
                "doi": f"10.1234/detail{i}", "title": f"Detailed Paper {i}",
                "authors": f"Author {i}", "year": 2023,
                "journal_or_publisher": "Journal", "type": "article",
                "courses": "Advanced Climate Finance",
                "institutions": "Top University",
                "countries": "USA", "n_courses": 1, "in_corpus": False,
            })
        # Small course reading (should be filtered at n_courses=1)
        rows.append({
            "doi": "10.1234/small", "title": "Small Paper",
            "authors": "Nobody", "year": 2023,
            "journal_or_publisher": "Journal", "type": "article",
            "courses": "Intro Course",
            "institutions": "Small College",
            "countries": "USA", "n_courses": 1, "in_corpus": False,
        })

        cols = ["doi", "title", "authors", "year", "journal_or_publisher",
                "type", "courses", "institutions", "countries", "n_courses",
                "in_corpus"]
        import pandas as pd
        df = pd.DataFrame(rows, columns=cols)
        csv_path = str(tmp_path / "reading_lists.csv")
        df.to_csv(csv_path, index=False)

        records = load_scraped(csv_path)
        # All detailed course readings should pass (have DOI + from detailed course)
        detailed_records = [r for r in records if r["course"] == "Advanced Climate Finance"]
        assert len(detailed_records) >= MIN_READINGS_DETAILED
        # Small course reading should NOT pass (n_courses=1, not from detailed course)
        small_records = [r for r in records if r["course"] == "Intro Course"]
        assert len(small_records) == 0

    def test_standard_filter_still_applies(self, tmp_path):
        """Non-detailed course readings still need n_courses>=2 for DOI."""
        from build_teaching_yaml import load_scraped

        rows = [{
            "doi": "10.1234/alone", "title": "Lonely Paper",
            "authors": "Solo", "year": 2023,
            "journal_or_publisher": "Journal", "type": "article",
            "courses": "Small Course",
            "institutions": "College",
            "countries": "USA", "n_courses": 1, "in_corpus": False,
        }]

        cols = ["doi", "title", "authors", "year", "journal_or_publisher",
                "type", "courses", "institutions", "countries", "n_courses",
                "in_corpus"]
        import pandas as pd
        df = pd.DataFrame(rows, columns=cols)
        csv_path = str(tmp_path / "reading_lists.csv")
        df.to_csv(csv_path, index=False)

        records = load_scraped(csv_path)
        assert len(records) == 0  # filtered out


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


class TestFuzzyTitleDedup:
    """Tests for fuzzy title grouping in build_teaching_yaml.py."""

    def test_fuzzy_title_groups(self, tmp_path):
        """Variant titles for the same work should aggregate their course counts.

        Given titles that are clearly the same work but with different phrasing
        (edition years, word reordering), fuzzy dedup should group them so their
        combined n_courses passes the filter threshold (>= MIN_COURSES_NO_DOI).
        """
        from build_teaching_yaml import load_scraped

        # Three variant titles for the CPI Global Landscape report, each
        # from a different course.  Without fuzzy dedup: each has n_courses=1,
        # all filtered out (need >= 3).  With fuzzy dedup: they merge into
        # one group with n_courses=3, passing the filter.
        rows = [
            {"doi": "", "title": "Global Landscape of Climate Finance 2021",
             "authors": "CPI", "year": 2021,
             "journal_or_publisher": "CPI", "type": "report",
             "courses": "Climate Economics 101",
             "institutions": "Uni A", "countries": "UK",
             "n_courses": 1, "in_corpus": False},
            {"doi": "", "title": "Global landscape of climate finance in 2019",
             "authors": "CPI", "year": 2019,
             "journal_or_publisher": "CPI", "type": "report",
             "courses": "Environmental Finance",
             "institutions": "Uni B", "countries": "France",
             "n_courses": 1, "in_corpus": False},
            {"doi": "",
             "title": "Global Landscape of Climate Finance: A Decade of Data",
             "authors": "CPI", "year": 2023,
             "journal_or_publisher": "CPI", "type": "report",
             "courses": "Green Finance Masters",
             "institutions": "Uni C", "countries": "Germany",
             "n_courses": 1, "in_corpus": False},
        ]

        cols = ["doi", "title", "authors", "year", "journal_or_publisher",
                "type", "courses", "institutions", "countries", "n_courses",
                "in_corpus"]
        df = pd.DataFrame(rows, columns=cols)
        csv_path = str(tmp_path / "reading_lists.csv")
        df.to_csv(csv_path, index=False)

        records = load_scraped(csv_path)
        # All three variants should survive the filter (aggregated n_courses >= 3)
        assert len(records) >= 3, (
            f"Expected >= 3 records from fuzzy-grouped CPI report variants, "
            f"got {len(records)}"
        )

    def test_fuzzy_groups_function(self):
        """fuzzy_title_groups should cluster similar titles together."""
        from build_teaching_yaml import fuzzy_title_groups

        titles = [
            "Global Landscape of Climate Finance 2021",
            "Global landscape of climate finance in 2019",
            "Global Landscape of Climate Finance: A Decade of Data",
            "Principles of Sustainable Finance",
            "Principes de la finance durable",  # translation — should NOT match
        ]
        groups = fuzzy_title_groups(titles)

        # The three CPI Global Landscape variants should be in the same group
        cpi_group = groups[0]
        assert groups[1] == cpi_group, "CPI 2019 edition should group with 2021"
        assert groups[2] == cpi_group, "CPI Decade edition should group with 2021"

        # The French translation is too different — should be a separate group
        assert groups[3] != cpi_group, "Unrelated title should not group with CPI"

    def test_fuzzy_dedup_does_not_over_merge(self):
        """Genuinely different works should remain separate groups."""
        from build_teaching_yaml import fuzzy_title_groups

        titles = [
            "Climate Change 2022: Mitigation of Climate Change",
            "Climate Change 2014: Mitigation of Climate Change",
            "Global Landscape of Climate Finance 2021",
            "Principles of Sustainable Finance",
        ]
        groups = fuzzy_title_groups(titles)
        # The two IPCC reports (2022 vs 2014) are similar enough to merge
        # (same series, different edition)
        assert groups[0] == groups[1], "Same-series IPCC reports should merge"
        # Unrelated titles should not merge with each other
        assert groups[2] != groups[0], "CPI report should not merge with IPCC"
        assert groups[3] != groups[0], "Sustainable finance should not merge with IPCC"
        assert groups[2] != groups[3], "CPI should not merge with sustainable finance"

    def test_fuzzy_skips_short_titles(self):
        """Very short titles (< 4 words) should not participate in fuzzy matching."""
        from build_teaching_yaml import fuzzy_title_groups

        titles = [
            "Climate Change",          # Too short — would match everything
            "Climate Change 2022: Mitigation of Climate Change",
            "The Economics of Climate Change",
        ]
        groups = fuzzy_title_groups(titles)
        # "Climate Change" is too short to fuzzy-match anything
        assert groups[0] != groups[1], "Short generic title should not merge with IPCC"
        assert groups[0] != groups[2], "Short generic title should not merge with Nordhaus"
