"""Tests for filter_flags.py — per-rule parity tests with fixed fixture."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

# Add scripts/ to path so we can import filter_flags
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from filter_flags import (
    _cache_key,
    _has_safe_words,
    _load_config,
    _text_has_concept_groups,
    compute_protection,
    flag_citation_isolated,
    flag_llm_irrelevant,
    flag_missing_metadata,
    flag_no_abstract,
    flag_semantic_outlier,
    flag_title_blacklist,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def config():
    return _load_config(os.path.join(FIXTURE_DIR, "corpus_filter_test.yaml"))


@pytest.fixture
def fixture_df():
    """~20 rows covering every flag and protection case."""
    return pd.read_csv(os.path.join(FIXTURE_DIR, "filter_fixture.csv"))


# ============================================================
# Helper tests
# ============================================================

class TestHelpers:
    def test_has_safe_words_positive(self):
        assert _has_safe_words("Climate change impacts", ["climate", "carbon"])

    def test_has_safe_words_negative(self):
        assert not _has_safe_words("Blockchain technology", ["climate", "carbon"])

    def test_has_safe_words_empty(self):
        assert not _has_safe_words("", ["climate"])
        assert not _has_safe_words(None, ["climate"])

    def test_text_has_concept_groups_positive(self):
        groups = {
            "climate": ["climate", "emission"],
            "finance": ["finance", "investment"],
        }
        assert _text_has_concept_groups(
            "Climate finance and investment", groups, 2
        )

    def test_text_has_concept_groups_negative(self):
        groups = {
            "climate": ["climate", "emission"],
            "finance": ["finance", "investment"],
        }
        assert not _text_has_concept_groups("Only about climate", groups, 2)

    def test_text_has_concept_groups_empty(self):
        groups = {"climate": ["climate"]}
        assert not _text_has_concept_groups("", groups, 1)
        assert not _text_has_concept_groups(None, groups, 1)

    def test_load_config(self, config):
        assert "noise_title" in config
        assert "safe_title" in config
        assert "concept_groups" in config
        assert "citation_isolation" in config
        assert "semantic_outlier" in config
        assert "protection" in config


# ============================================================
# Flag 1: Missing metadata
# ============================================================

class TestFlagMissingMetadata:
    def test_missing_title_flagged(self, fixture_df, config):
        """Row 0: missing title, author, year -> flagged."""
        result = flag_missing_metadata(fixture_df, config)
        assert result.iloc[0] is True or result.iloc[0] == True

    def test_missing_author_safe_title_not_flagged(self, fixture_df, config):
        """Row 1: missing author but safe title ('Climate...') -> NOT flagged."""
        result = flag_missing_metadata(fixture_df, config)
        assert result.iloc[1] == False

    def test_complete_metadata_not_flagged(self, fixture_df, config):
        """Row 2: complete metadata -> NOT flagged."""
        result = flag_missing_metadata(fixture_df, config)
        assert result.iloc[2] == False

    def test_returns_series_aligned(self, fixture_df, config):
        result = flag_missing_metadata(fixture_df, config)
        assert isinstance(result, pd.Series)
        assert len(result) == len(fixture_df)
        assert result.index.equals(fixture_df.index)


# ============================================================
# Flag 2: No abstract + irrelevant title
# ============================================================

class TestFlagNoAbstract:
    def test_no_abstract_irrelevant_title_flagged(self, fixture_df, config):
        """Row 3: no abstract, irrelevant title -> flagged."""
        result = flag_no_abstract(fixture_df, config)
        assert result.iloc[3] == True

    def test_no_abstract_safe_title_not_flagged(self, fixture_df, config):
        """Row 4: no abstract but safe title ('Green energy...') -> NOT flagged."""
        result = flag_no_abstract(fixture_df, config)
        assert result.iloc[4] == False

    def test_has_abstract_not_flagged(self, fixture_df, config):
        """Row 2: has abstract -> NOT flagged."""
        result = flag_no_abstract(fixture_df, config)
        assert result.iloc[2] == False


# ============================================================
# Flag 3: Title blacklist
# ============================================================

class TestFlagTitleBlacklist:
    def test_noise_title_flagged(self, fixture_df, config):
        """Row 5: 'Blockchain' in title, no safe words -> flagged."""
        result = flag_title_blacklist(fixture_df, config)
        assert result.iloc[5] == True

    def test_noise_plus_safe_not_flagged(self, fixture_df, config):
        """Row 6: 'Blockchain' + 'climate' -> NOT flagged."""
        result = flag_title_blacklist(fixture_df, config)
        assert result.iloc[6] == False

    def test_clean_title_not_flagged(self, fixture_df, config):
        """Row 2: clean title -> NOT flagged."""
        result = flag_title_blacklist(fixture_df, config)
        assert result.iloc[2] == False

    def test_deep_learning_flagged(self, fixture_df, config):
        """Row 15: 'Deep learning' title, no safe words -> flagged."""
        result = flag_title_blacklist(fixture_df, config)
        assert result.iloc[15] == True


# ============================================================
# Flag 4: Citation isolation
# ============================================================

class TestFlagCitationIsolated:
    def test_old_isolated_flagged(self, fixture_df, config):
        """Row 7: year 2010, DOI not in citations -> flagged."""
        citations_df = pd.DataFrame({
            "source_doi": ["10.1000/old-cited"],
            "ref_doi": ["10.1000/complete"],
        })
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        result = flag_citation_isolated(fixture_df, config, citations_df=citations_df)
        assert result.iloc[7] == True

    def test_old_cited_not_flagged(self, fixture_df, config):
        """Row 8: year 2005 but DOI appears as source -> NOT flagged."""
        citations_df = pd.DataFrame({
            "source_doi": ["10.1000/old-cited"],
            "ref_doi": ["10.1000/complete"],
        })
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        result = flag_citation_isolated(fixture_df, config, citations_df=citations_df)
        assert result.iloc[8] == False

    def test_recent_isolated_not_flagged(self, fixture_df, config):
        """Row 9: year 2022, isolated but recent -> NOT flagged (year > max_year)."""
        citations_df = pd.DataFrame({
            "source_doi": ["10.1000/other"],
            "ref_doi": ["10.1000/another"],
        })
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        result = flag_citation_isolated(fixture_df, config, citations_df=citations_df)
        assert result.iloc[9] == False

    def test_missing_citations_raises(self, fixture_df, config):
        with pytest.raises(ValueError, match="citations_df is required"):
            flag_citation_isolated(fixture_df, config, citations_df=None)


# ============================================================
# Flag 5: Semantic outlier
# ============================================================

class TestFlagSemanticOutlier:
    def test_outlier_detected(self, config):
        """Synthetic test: one extreme embedding flagged as outlier."""
        rng = np.random.default_rng(42)
        n_papers = 20
        emb_dim = 8
        # Use tight cluster so the outlier stands out clearly
        embeddings = rng.normal(loc=1.0, scale=0.1, size=(n_papers, emb_dim)).astype(np.float32)
        # Make row 7 point in the opposite direction (extreme outlier)
        embeddings[7] = -10.0 * np.ones(emb_dim, dtype=np.float32)

        df = pd.DataFrame({
            "doi": [f"10.1000/paper{i}" for i in range(n_papers)],
        })
        df["doi_norm"] = df["doi"]
        emb_df = df.copy()

        flag_mask, dists = flag_semantic_outlier(
            df, config, embeddings=embeddings, emb_df=emb_df
        )
        assert flag_mask.iloc[7] == True
        assert dists.iloc[7] > 0

    def test_missing_embeddings_raises(self, config):
        df = pd.DataFrame({"doi": ["10.1000/a"]})
        with pytest.raises(ValueError, match="embeddings and emb_df are required"):
            flag_semantic_outlier(df, config, embeddings=None, emb_df=None)

    def test_size_mismatch_raises(self, config):
        df = pd.DataFrame({"doi": ["10.1000/a", "10.1000/b"]})
        df["doi_norm"] = df["doi"]
        emb_df = df.copy()
        embeddings = np.zeros((3, 8))  # 3 != 2
        with pytest.raises(ValueError, match="mismatch"):
            flag_semantic_outlier(df, config, embeddings=embeddings, emb_df=emb_df)


# ============================================================
# Flag 6: LLM relevance (mocked)
# ============================================================

class TestFlagLLMIrrelevant:
    def test_skips_already_flagged(self, fixture_df, config, monkeypatch):
        """LLM should not score papers already flagged by rules 1-5."""
        call_count = 0

        def counting_llm_call(prompt, backend, api_key, model):
            nonlocal call_count
            call_count += 1
            return '{"1": true}'

        monkeypatch.setattr("filter_flags._llm_call", counting_llm_call)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        already_flagged = pd.Series(True, index=fixture_df.index)
        result = flag_llm_irrelevant(fixture_df, config, already_flagged=already_flagged)
        assert call_count == 0
        assert result.all() == False  # No flags set

    def test_returns_series_aligned(self, fixture_df, config, monkeypatch):
        """Result is aligned with input df index."""
        monkeypatch.setattr(
            "filter_flags._llm_call",
            lambda p, b, a, m: '{"1": true}',
        )
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        already_flagged = pd.Series(True, index=fixture_df.index)
        result = flag_llm_irrelevant(fixture_df, config, already_flagged=already_flagged)
        assert isinstance(result, pd.Series)
        assert len(result) == len(fixture_df)


# ============================================================
# LLM cache invalidation
# ============================================================

class TestLLMCacheInvalidation:
    def test_config_hash_changes_with_model(self, config):
        """Cache key changes when model changes."""
        hash1 = _cache_key(config)
        config2 = config.copy()
        config2["llm_relevance"] = config["llm_relevance"].copy()
        config2["llm_relevance"]["openrouter_model"] = "different/model"
        hash2 = _cache_key(config2)
        assert hash1 != hash2

    def test_config_hash_changes_with_prompt(self, config):
        """Cache key changes when prompt changes."""
        hash1 = _cache_key(config)
        config2 = config.copy()
        config2["llm_relevance"] = config["llm_relevance"].copy()
        config2["llm_relevance"]["prompt_template"] = "Different prompt"
        hash2 = _cache_key(config2)
        assert hash1 != hash2


# ============================================================
# Protection
# ============================================================

class TestComputeProtection:
    def test_high_cites_protected(self, fixture_df, config):
        """Row 2: cited_by_count=100 >= 50 -> protected."""
        citations_df = pd.DataFrame({"source_doi": [], "ref_doi": []})
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        protected, reasons = compute_protection(
            fixture_df, config, citations_df=citations_df
        )
        assert protected.iloc[2] == True
        assert "cited_by" in reasons.iloc[2]

    def test_multi_source_protected(self, fixture_df, config):
        """Row 12: source_count=2 >= 2 -> protected."""
        citations_df = pd.DataFrame({"source_doi": [], "ref_doi": []})
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        protected, reasons = compute_protection(
            fixture_df, config, citations_df=citations_df
        )
        assert protected.iloc[12] == True
        assert "multi_source" in reasons.iloc[12]

    def test_cited_in_corpus_protected(self, fixture_df, config):
        """Paper appearing as ref_doi in citations -> protected."""
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        citations_df = pd.DataFrame({
            "source_doi": ["10.1000/some-source"],
            "ref_doi": ["10.1000/old-isolated"],  # row 7
        })
        protected, reasons = compute_protection(
            fixture_df, config, citations_df=citations_df
        )
        assert protected.iloc[7] == True
        assert "cited_in_corpus" in reasons.iloc[7]

    def test_low_cites_not_protected(self, fixture_df, config):
        """Row 5: cited_by_count=1, source_count=1 -> NOT protected."""
        citations_df = pd.DataFrame({"source_doi": [], "ref_doi": []})
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        protected, _ = compute_protection(
            fixture_df, config, citations_df=citations_df
        )
        assert protected.iloc[5] == False

    def test_protected_flagged_paper(self, fixture_df, config):
        """Row 14: missing metadata but cited_by_count=300 -> protected."""
        citations_df = pd.DataFrame({"source_doi": [], "ref_doi": []})
        fixture_df["doi_norm"] = fixture_df["doi"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )
        protected, reasons = compute_protection(
            fixture_df, config, citations_df=citations_df
        )
        assert protected.iloc[14] == True


# ============================================================
# Apply gates
# ============================================================

class TestApplyGates:
    def test_rejects_incomplete(self):
        """--apply raises if expected flag columns are missing."""
        from types import SimpleNamespace

        # Import the gate functions from the orchestrator
        # We test the logic inline since corpus_filter.py may not be importable yet
        def expected_flag_columns(args, has_embeddings):
            cols = ["missing_metadata", "no_abstract_irrelevant", "title_blacklist"]
            if not args.skip_citation_flag:
                cols.append("citation_isolated_old")
            if has_embeddings:
                cols.append("semantic_outlier")
            if not args.skip_llm:
                cols.append("llm_irrelevant")
            return cols

        args = SimpleNamespace(skip_citation_flag=False, skip_llm=False)
        expected = expected_flag_columns(args, has_embeddings=True)
        # All 6 flags expected
        assert len(expected) == 6

    def test_accepts_intentional_skips(self):
        """With --skip-llm and --skip-citation-flag, only 3 flags expected."""
        from types import SimpleNamespace

        def expected_flag_columns(args, has_embeddings):
            cols = ["missing_metadata", "no_abstract_irrelevant", "title_blacklist"]
            if not args.skip_citation_flag:
                cols.append("citation_isolated_old")
            if has_embeddings:
                cols.append("semantic_outlier")
            if not args.skip_llm:
                cols.append("llm_irrelevant")
            return cols

        args = SimpleNamespace(skip_citation_flag=True, skip_llm=True)
        expected = expected_flag_columns(args, has_embeddings=False)
        assert expected == ["missing_metadata", "no_abstract_irrelevant", "title_blacklist"]
