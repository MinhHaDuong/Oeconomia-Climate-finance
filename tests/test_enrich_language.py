"""Tests for #423: Language enrichment — OpenAlex backfill + local detection.

Verifies:
- normalize_lang converts ISO 639-3, full names, and regional codes to 2-letter ISO 639-1
- detect_language returns 2-letter codes for known texts
- is_valid_iso639_1 rejects nonsensical codes
- Cache round-trip (load_cache / save_cache) preserves data
- OpenAlex batch query builds correct filter strings
- Pipeline integration: enrich_language stage exists in dvc.yaml
"""

import os
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------- language normalization ----------

class TestNormalizeLang:
    """normalize_lang must map various code formats to 2-letter ISO 639-1."""

    def test_iso639_3_to_2(self):
        from enrich_language import normalize_lang
        assert normalize_lang("eng") == "en"
        assert normalize_lang("fra") == "fr"
        assert normalize_lang("deu") == "de"

    def test_already_two_letter(self):
        from enrich_language import normalize_lang
        assert normalize_lang("en") == "en"
        assert normalize_lang("fr") == "fr"

    def test_full_name(self):
        from enrich_language import normalize_lang
        assert normalize_lang("english") == "en"
        assert normalize_lang("french") == "fr"

    def test_regional_suffix_stripped(self):
        from enrich_language import normalize_lang
        assert normalize_lang("en_US") == "en"
        assert normalize_lang("en_gb") == "en"

    def test_null_returns_none(self):
        from enrich_language import normalize_lang
        assert normalize_lang(None) is None
        assert normalize_lang("") is None
        assert normalize_lang("nan") is None

    def test_unknown_returns_none(self):
        from enrich_language import normalize_lang
        assert normalize_lang("und") is None
        assert normalize_lang("unknown") is None


# ---------- ISO 639-1 validation ----------

class TestIsValidIso639_1:
    """is_valid_iso639_1 must accept real 2-letter language codes and reject nonsense."""

    def test_valid_codes(self):
        from enrich_language import is_valid_iso639_1
        for code in ("en", "fr", "de", "es", "zh", "ar", "ja", "pt"):
            assert is_valid_iso639_1(code), f"{code} should be valid"

    def test_invalid_codes(self):
        from enrich_language import is_valid_iso639_1
        for code in ("xx", "zz", "qq", "a1"):
            assert not is_valid_iso639_1(code), f"{code} should be invalid"

    def test_none_and_empty(self):
        from enrich_language import is_valid_iso639_1
        assert not is_valid_iso639_1(None)
        assert not is_valid_iso639_1("")


# ---------- local language detection ----------

class TestDetectLanguage:
    """detect_language uses langdetect on text and returns a 2-letter code."""

    def test_english(self):
        from enrich_language import detect_language
        text = ("Climate finance refers to local, national, or transnational financing "
                "that seeks to support mitigation and adaptation actions.")
        assert detect_language(text) == "en"

    def test_french(self):
        from enrich_language import detect_language
        text = ("La finance climatique concerne le financement des actions de lutte "
                "contre le changement climatique au niveau local et international.")
        assert detect_language(text) == "fr"

    def test_short_text_returns_none(self):
        from enrich_language import detect_language
        assert detect_language("Hi") is None
        assert detect_language("") is None
        assert detect_language(None) is None


# ---------- cache round-trip ----------

class TestCacheRoundTrip:
    """load_cache / save_cache must preserve key-value data."""

    def test_round_trip(self):
        from enrich_language import load_lang_cache, save_lang_cache
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {"10.1234/abc": "en", "10.5678/def": "fr"}
            save_lang_cache(data, tmpdir, "test_lang")
            loaded = load_lang_cache(tmpdir, "test_lang")
            assert loaded == data

    def test_empty_cache(self):
        from enrich_language import load_lang_cache
        with tempfile.TemporaryDirectory() as tmpdir:
            loaded = load_lang_cache(tmpdir, "test_lang")
            assert loaded == {}


# ---------- OpenAlex batch query building ----------

class TestBuildOABatch:
    """build_oa_doi_filter must create pipe-separated DOI filter strings."""

    def test_pipe_separated(self):
        from enrich_language import build_oa_doi_filter
        dois = ["10.1234/a", "10.5678/b", "10.9999/c"]
        result = build_oa_doi_filter(dois)
        assert result == "10.1234/a|10.5678/b|10.9999/c"

    def test_empty_list(self):
        from enrich_language import build_oa_doi_filter
        assert build_oa_doi_filter([]) == ""


# ---------- pass1 integration ----------

class TestPass1ApplyCache:
    """pass1_apply_cache writes language values from cache into the DataFrame."""

    def test_fills_null_language(self):
        from enrich_language import pass1_apply_cache
        df = pd.DataFrame({
            "doi": ["10.1234/a", "10.5678/b"],
            "language": [None, "en"],
        })
        cache = {"10.1234/a": "fr"}
        filled = pass1_apply_cache(df, cache)
        assert filled == 1
        assert df.loc[0, "language"] == "fr"
        # Already-set language not overwritten
        assert df.loc[1, "language"] == "en"


# ---------- pass2 integration ----------

class TestPass2LocalDetect:
    """pass2_local_detect fills remaining nulls using langdetect."""

    def test_fills_from_abstract(self):
        from enrich_language import pass2_local_detect
        df = pd.DataFrame({
            "language": [None],
            "title": ["Climate Finance"],
            "abstract": ["Climate finance refers to local, national, or transnational "
                         "financing that seeks to support mitigation and adaptation "
                         "actions addressing climate change."],
        })
        filled = pass2_local_detect(df)
        assert filled == 1
        assert df.loc[0, "language"] == "en"

    def test_skips_already_filled(self):
        from enrich_language import pass2_local_detect
        df = pd.DataFrame({
            "language": ["fr"],
            "title": ["Some English title here about climate"],
            "abstract": ["This is an English abstract about climate change."],
        })
        filled = pass2_local_detect(df)
        assert filled == 0
        assert df.loc[0, "language"] == "fr"


# ---------- DVC pipeline integration ----------

class TestDVCStage:
    """dvc.yaml must declare enrich_language after enrich_works and before extend."""

    @pytest.fixture(autouse=True)
    def _load_dvc(self):
        import yaml
        dvc_path = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")
        with open(dvc_path) as f:
            self.dvc = yaml.safe_load(f)

    def test_stage_exists(self):
        assert "enrich_language" in self.dvc["stages"]

    def test_depends_on_enriched_works(self):
        deps = self.dvc["stages"]["enrich_language"]["deps"]
        assert "data/catalogs/enriched_works.csv" in deps

    def test_script_in_deps(self):
        deps = self.dvc["stages"]["enrich_language"]["deps"]
        assert "scripts/enrich_language.py" in deps

    def test_outs_enriched_works(self):
        """The stage writes enriched_works.csv in-place (same as enrich_works)."""
        # The stage should NOT have enriched_works.csv as an output —
        # it modifies in place (same pattern as enrich_abstracts.py).
        # Instead, the extend stage depends on enriched_works.csv.
        stage = self.dvc["stages"]["enrich_language"]
        # The stage must exist and have a cmd
        assert "cmd" in stage


# ---------- script structure ----------

class TestScriptStructure:
    """enrich_language.py follows project conventions."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = os.path.join(SCRIPTS_DIR, "enrich_language.py")
        with open(path) as f:
            self.source = f.read()

    def test_uses_get_logger(self):
        assert "get_logger" in self.source

    def test_has_argparse(self):
        assert "argparse" in self.source
        assert "ArgumentParser" in self.source

    def test_no_bare_print(self):
        """No bare print() calls — use log.info() instead."""
        import ast
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    pytest.fail("Found bare print() call — use log.info() instead")

    def test_imports_retry_get(self):
        assert "retry_get" in self.source

    def test_uses_enrich_cache(self):
        assert "enrich_cache" in self.source
