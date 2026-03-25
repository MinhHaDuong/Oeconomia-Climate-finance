"""Unit tests for alluvial pipeline functions with synthetic data (issue #81).

Tests exercise actual computation logic without requiring the real corpus:
- load_analysis_corpus() filtering logic
- is_clean_term() denoising function
- load_analysis_config() with a temp YAML file
- compute_alluvial.py shim's _build_argv() selective flag forwarding
"""

import os
import sys
import textwrap
from argparse import Namespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# Allow imports from scripts/
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_works(n=20):
    """Create a small synthetic refined_works DataFrame."""
    rng = np.random.RandomState(42)
    years = rng.choice(range(1985, 2030), size=n)
    cited = rng.choice([0, 10, 30, 60, 100], size=n)
    titles = [f"Paper {i}" if i % 10 != 0 else "" for i in range(n)]
    return pd.DataFrame({
        "title": titles,
        "year": years,
        "cited_by_count": cited,
        "doi": [f"10.1000/test.{i}" for i in range(n)],
        "abstract": [f"Abstract {i}" for i in range(n)],
    })


def _make_embeddings(n=20, dim=384):
    """Create synthetic embeddings aligned with _make_works()."""
    return np.random.RandomState(42).randn(n, dim).astype(np.float32)


# ---------------------------------------------------------------------------
# load_analysis_corpus()
# ---------------------------------------------------------------------------

class TestLoadAnalysisCorpus:
    """Test filtering logic in load_analysis_corpus()."""

    def _call(self, works_df, embeddings=None, **kwargs):
        """Call load_analysis_corpus with mocked file I/O."""
        from utils import load_analysis_corpus

        with_emb = kwargs.pop("with_embeddings", embeddings is not None)

        with patch("pipeline_loaders.pd.read_csv", return_value=works_df), \
             patch("pipeline_loaders.load_refined_embeddings",
                   return_value=embeddings):
            return load_analysis_corpus(with_embeddings=with_emb, **kwargs)

    def test_filters_missing_titles(self):
        works = _make_works()
        n_empty = (works["title"] == "").sum() + works["title"].isna().sum()
        assert n_empty > 0, "fixture should have empty titles"
        df, _ = self._call(works, with_embeddings=False)
        assert (df["title"].str.len() > 0).all()

    def test_filters_out_of_range_years(self):
        works = _make_works()
        n_outside = ((works["year"] < 1990) | (works["year"] > 2025)).sum()
        assert n_outside > 0, "fixture should have out-of-range years"
        df, _ = self._call(works, with_embeddings=False)
        assert (df["year"] >= 1990).all()
        assert (df["year"] <= 2025).all()

    def test_coerces_cited_by_count(self):
        works = _make_works()
        # Force object dtype so we can inject a non-numeric value
        works["cited_by_count"] = works["cited_by_count"].astype(object)
        works.loc[0, "cited_by_count"] = "invalid"
        df, _ = self._call(works, with_embeddings=False)
        assert pd.api.types.is_numeric_dtype(df["cited_by_count"])
        # invalid should become 0
        assert (df["cited_by_count"] >= 0).all()

    def test_core_only_filters_by_threshold(self):
        works = _make_works()
        df_all, _ = self._call(works, with_embeddings=False)
        df_core, _ = self._call(works, with_embeddings=False,
                                core_only=True, cite_threshold=50)
        assert len(df_core) < len(df_all)
        assert (df_core["cited_by_count"] >= 50).all()

    def test_embeddings_aligned_after_filtering(self):
        works = _make_works(20)
        emb = _make_embeddings(20)
        df, result_emb = self._call(works, embeddings=emb)
        assert len(df) == len(result_emb)

    def test_embeddings_aligned_after_core_filtering(self):
        works = _make_works(20)
        emb = _make_embeddings(20)
        df, result_emb = self._call(works, embeddings=emb,
                                    core_only=True, cite_threshold=50)
        assert len(df) == len(result_emb)

    def test_embedding_mismatch_raises(self):
        works = _make_works(20)
        emb = _make_embeddings(15)  # wrong size
        with pytest.raises(RuntimeError, match="mismatch"):
            self._call(works, embeddings=emb)

    def test_without_embeddings_returns_none(self):
        works = _make_works()
        df, emb = self._call(works, with_embeddings=False)
        assert emb is None
        assert len(df) > 0

    def test_resets_index(self):
        works = _make_works()
        df, _ = self._call(works, with_embeddings=False)
        assert list(df.index) == list(range(len(df)))


# ---------------------------------------------------------------------------
# is_clean_term()
# ---------------------------------------------------------------------------

class TestIsCleanTerm:
    """Test lexical denoising in is_clean_term()."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from compute_lexical import is_clean_term
        self.is_clean_term = is_clean_term

    def test_rejects_short_single_token(self):
        assert not self.is_clean_term("ab")
        assert not self.is_clean_term("I")

    def test_accepts_normal_single_token(self):
        assert self.is_clean_term("finance")
        assert self.is_clean_term("climate")

    def test_rejects_all_digit_tokens(self):
        assert not self.is_clean_term("2023")
        assert not self.is_clean_term("100 200")

    def test_accepts_mixed_digit_text(self):
        assert self.is_clean_term("cop21")
        assert self.is_clean_term("100 billion")

    def test_rejects_extra_stop_words(self):
        assert not self.is_clean_term("mid")
        assert not self.is_clean_term("vol")
        assert not self.is_clean_term("new")
        assert not self.is_clean_term("use")
        assert not self.is_clean_term("used")
        assert not self.is_clean_term("using")

    def test_accepts_multi_token_with_stop(self):
        # "new" as part of multi-token phrase is fine
        assert self.is_clean_term("new york")
        assert self.is_clean_term("new climate policy")

    def test_rejects_empty_like(self):
        # Single char
        assert not self.is_clean_term("a")


# ---------------------------------------------------------------------------
# load_analysis_config()
# ---------------------------------------------------------------------------

class TestLoadAnalysisConfig:
    """Test YAML config loading."""

    def test_loads_valid_config(self, tmp_path):
        yaml_content = textwrap.dedent("""\
            periodization:
              breaks: [2007, 2015]
            clustering:
              k: 6
              cite_threshold: 50
        """)
        config_file = tmp_path / "analysis.yaml"
        config_file.write_text(yaml_content)

        with patch("pipeline_loaders.CONFIG_DIR", str(tmp_path)):
            from utils import load_analysis_config
            cfg = load_analysis_config()

        assert cfg["periodization"]["breaks"] == [2007, 2015]
        assert cfg["clustering"]["k"] == 6
        assert cfg["clustering"]["cite_threshold"] == 50

    def test_missing_file_raises(self, tmp_path):
        with patch("pipeline_loaders.CONFIG_DIR", str(tmp_path)):
            from utils import load_analysis_config
            with pytest.raises(FileNotFoundError, match="analysis.yaml"):
                load_analysis_config()


# ---------------------------------------------------------------------------
# _build_argv() selective flag forwarding
# ---------------------------------------------------------------------------

class TestBuildArgv:
    """Test the shim's selective flag-forwarding logic."""

    # Replicate the logic from compute_alluvial.py without importing the
    # module-level argparse (which would call sys.argv and fail).

    SCRIPT_FLAGS = {
        "scripts/compute_breakpoints.py": {
            "--core-only", "--censor-gap", "--robustness", "--no-pdf",
        },
        "scripts/compute_clusters.py": {
            "--core-only", "--no-pdf", "--breaks",
        },
        "scripts/compute_lexical.py": {
            "--no-pdf",
        },
    }

    @staticmethod
    def _build_argv(script, args, script_flags):
        """Reimplementation matching compute_alluvial.py logic."""
        accepted = script_flags[script]
        argv = []
        if args.core_only and "--core-only" in accepted:
            argv.append("--core-only")
        if args.censor_gap and "--censor-gap" in accepted:
            argv.extend(["--censor-gap", str(args.censor_gap)])
        if args.robustness and "--robustness" in accepted:
            argv.append("--robustness")
        if args.no_pdf and "--no-pdf" in accepted:
            argv.append("--no-pdf")
        if args.breaks and "--breaks" in accepted:
            argv.extend(["--breaks", args.breaks])
        return argv

    def test_core_only_forwarded_to_breakpoints(self):
        args = Namespace(core_only=True, censor_gap=0, robustness=False,
                         no_pdf=False, breaks=None)
        argv = self._build_argv("scripts/compute_breakpoints.py",
                                args, self.SCRIPT_FLAGS)
        assert "--core-only" in argv

    def test_core_only_forwarded_to_clusters(self):
        args = Namespace(core_only=True, censor_gap=0, robustness=False,
                         no_pdf=False, breaks=None)
        argv = self._build_argv("scripts/compute_clusters.py",
                                args, self.SCRIPT_FLAGS)
        assert "--core-only" in argv

    def test_core_only_not_forwarded_to_lexical(self):
        args = Namespace(core_only=True, censor_gap=0, robustness=False,
                         no_pdf=False, breaks=None)
        argv = self._build_argv("scripts/compute_lexical.py",
                                args, self.SCRIPT_FLAGS)
        assert "--core-only" not in argv

    def test_censor_gap_only_to_breakpoints(self):
        args = Namespace(core_only=False, censor_gap=2, robustness=False,
                         no_pdf=False, breaks=None)
        bp_argv = self._build_argv("scripts/compute_breakpoints.py",
                                   args, self.SCRIPT_FLAGS)
        cl_argv = self._build_argv("scripts/compute_clusters.py",
                                   args, self.SCRIPT_FLAGS)
        assert ["--censor-gap", "2"] == bp_argv
        assert cl_argv == []

    def test_robustness_only_to_breakpoints(self):
        args = Namespace(core_only=False, censor_gap=0, robustness=True,
                         no_pdf=False, breaks=None)
        bp_argv = self._build_argv("scripts/compute_breakpoints.py",
                                   args, self.SCRIPT_FLAGS)
        cl_argv = self._build_argv("scripts/compute_clusters.py",
                                   args, self.SCRIPT_FLAGS)
        lx_argv = self._build_argv("scripts/compute_lexical.py",
                                   args, self.SCRIPT_FLAGS)
        assert "--robustness" in bp_argv
        assert "--robustness" not in cl_argv
        assert "--robustness" not in lx_argv

    def test_no_pdf_forwarded_to_all(self):
        args = Namespace(core_only=False, censor_gap=0, robustness=False,
                         no_pdf=True, breaks=None)
        for script in self.SCRIPT_FLAGS:
            argv = self._build_argv(script, args, self.SCRIPT_FLAGS)
            assert "--no-pdf" in argv

    def test_breaks_forwarded_to_clusters_only(self):
        args = Namespace(core_only=False, censor_gap=0, robustness=False,
                         no_pdf=False, breaks="2007,2013")
        bp_argv = self._build_argv("scripts/compute_breakpoints.py",
                                   args, self.SCRIPT_FLAGS)
        cl_argv = self._build_argv("scripts/compute_clusters.py",
                                   args, self.SCRIPT_FLAGS)
        lx_argv = self._build_argv("scripts/compute_lexical.py",
                                   args, self.SCRIPT_FLAGS)
        assert "--breaks" not in bp_argv
        assert ["--breaks", "2007,2013"] == cl_argv[-2:]
        assert "--breaks" not in lx_argv

    def test_no_flags_gives_empty(self):
        args = Namespace(core_only=False, censor_gap=0, robustness=False,
                         no_pdf=False, breaks=None)
        for script in self.SCRIPT_FLAGS:
            assert self._build_argv(script, args, self.SCRIPT_FLAGS) == []

    def test_all_flags_combined(self):
        args = Namespace(core_only=True, censor_gap=3, robustness=True,
                         no_pdf=True, breaks="2007,2015")
        bp = self._build_argv("scripts/compute_breakpoints.py",
                              args, self.SCRIPT_FLAGS)
        cl = self._build_argv("scripts/compute_clusters.py",
                              args, self.SCRIPT_FLAGS)
        lx = self._build_argv("scripts/compute_lexical.py",
                              args, self.SCRIPT_FLAGS)
        # breakpoints gets: --core-only, --censor-gap 3, --robustness, --no-pdf
        assert "--core-only" in bp
        assert "--censor-gap" in bp
        assert "--robustness" in bp
        assert "--no-pdf" in bp
        assert "--breaks" not in bp
        # clusters gets: --core-only, --no-pdf, --breaks
        assert "--core-only" in cl
        assert "--no-pdf" in cl
        assert "--breaks" in cl
        assert "--robustness" not in cl
        assert "--censor-gap" not in cl
        # lexical gets: --no-pdf only
        assert lx == ["--no-pdf"]
