"""Tests for LLM abstract summarization (#415).

~230 records have abstracts >1000 tokens that are full introductions, book
reviews, or correction notices — not real abstracts. This script generates
proper abstract-length summaries via LLM, cached in enrich_cache/.

Exit criteria (from ticket):
- All too_long records get a generated summary under 400 tokens
- Summaries preserve key terms from the original
"""

import json
import os
import sys
import tempfile

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from summarize_abstracts import (
    TOKEN_LIMIT,
    classify_abstract_length,
    generate_summary,
    load_summary_cache,
    save_summary_cache,
    summarize_too_long_abstracts,
)


# ============================================================
# Fixtures
# ============================================================

LONG_ABSTRACT = (
    "Climate finance has emerged as a critical area of international "
    "negotiations. " * 80  # ~960 words ≈ ~1200 tokens
)

SHORT_ABSTRACT = "This paper studies climate finance flows to developing countries."

MEDIUM_ABSTRACT = (
    "We analyze the evolution of climate finance from 2000 to 2020. "
    "Our corpus includes 30,000 academic papers and policy documents. "
    "Results show three distinct periods of growth."
)


@pytest.fixture
def sample_df():
    """DataFrame with a mix of abstract lengths."""
    return pd.DataFrame({
        "doi": ["10.1000/long", "10.1000/short", "10.1000/medium",
                "10.1000/missing", "10.1000/long2"],
        "title": ["Long paper", "Short paper", "Medium paper",
                  "No abstract", "Another long one"],
        "abstract": [LONG_ABSTRACT, SHORT_ABSTRACT, MEDIUM_ABSTRACT,
                     None, LONG_ABSTRACT + " Extra content here."],
    })


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Temporary directory for cache files."""
    return str(tmp_path)


# ============================================================
# Tests: classification
# ============================================================

def test_classify_too_long():
    """Abstracts exceeding TOKEN_LIMIT are classified as too_long."""
    assert classify_abstract_length(LONG_ABSTRACT) == "too_long"


def test_classify_normal():
    """Normal-length abstracts are classified as ok."""
    assert classify_abstract_length(SHORT_ABSTRACT) == "ok"
    assert classify_abstract_length(MEDIUM_ABSTRACT) == "ok"


def test_classify_missing():
    """Missing/empty abstracts are classified as missing."""
    assert classify_abstract_length(None) == "missing"
    assert classify_abstract_length("") == "missing"
    assert classify_abstract_length(float("nan")) == "missing"


# ============================================================
# Tests: cache round-trip
# ============================================================

def test_cache_round_trip(tmp_cache_dir):
    """Cache saves and loads correctly (JSONL format)."""
    cache = {
        "10.1000/a": {"summary": "Short summary.", "model": "test/model",
                       "tokens_original": 1500, "error": None},
        "10.1000/b": {"summary": "Another one.", "model": "test/model",
                       "tokens_original": 1200, "error": None},
    }
    path = os.path.join(tmp_cache_dir, "abstract_summaries_cache.jsonl")
    save_summary_cache(cache, path)
    loaded = load_summary_cache(path)
    assert loaded == cache


def test_cache_empty_file(tmp_cache_dir):
    """Loading a non-existent cache returns empty dict."""
    path = os.path.join(tmp_cache_dir, "nonexistent.jsonl")
    assert load_summary_cache(path) == {}


# ============================================================
# Tests: summary generation (mocked LLM)
# ============================================================

def test_generate_summary_under_400_tokens(monkeypatch):
    """Generated summary must be under 400 tokens."""
    fake_summary = (
        "This paper examines the evolution of climate finance in "
        "international negotiations, tracing its emergence as a key "
        "policy area from the early 2000s through 2020."
    )

    def mock_completion(**kwargs):
        class Choice:
            class Message:
                content = fake_summary
            message = Message()
        class Response:
            choices = [Choice()]
        return Response()

    monkeypatch.setattr("summarize_abstracts.litellm.completion", mock_completion)

    result = generate_summary(LONG_ABSTRACT, model="test/model")
    assert result["error"] is None
    assert len(result["summary"].split()) < 400  # word-level check
    assert "climate finance" in result["summary"].lower()


def test_generate_summary_preserves_key_terms(monkeypatch):
    """Summary must preserve key terms from the original."""
    original = (
        "The Green Climate Fund (GCF) and the Adaptation Fund have become "
        "central institutions in the architecture of climate finance. "
        "This paper traces their evolution from UNFCCC negotiations. " * 40
    )

    fake_summary = (
        "This paper traces the evolution of the Green Climate Fund (GCF) "
        "and the Adaptation Fund as central institutions in climate finance "
        "architecture, emerging from UNFCCC negotiations."
    )

    def mock_completion(**kwargs):
        class Choice:
            class Message:
                content = fake_summary
            message = Message()
        class Response:
            choices = [Choice()]
        return Response()

    monkeypatch.setattr("summarize_abstracts.litellm.completion", mock_completion)

    result = generate_summary(original, model="test/model")
    assert "green climate fund" in result["summary"].lower()
    assert "adaptation fund" in result["summary"].lower()


def test_generate_summary_handles_llm_error(monkeypatch):
    """LLM errors are captured, not raised."""
    def mock_completion(**kwargs):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr("summarize_abstracts.litellm.completion", mock_completion)

    result = generate_summary(LONG_ABSTRACT, model="test/model")
    assert result["error"] is not None
    assert result["summary"] == ""


# ============================================================
# Tests: end-to-end (mocked LLM)
# ============================================================

def test_summarize_too_long_abstracts_e2e(monkeypatch, sample_df, tmp_cache_dir):
    """All too_long records get summaries; others are untouched."""
    fake_summary = "A concise summary of climate finance negotiations."

    def mock_completion(**kwargs):
        class Choice:
            class Message:
                content = fake_summary
            message = Message()
        class Response:
            choices = [Choice()]
        return Response()

    monkeypatch.setattr("summarize_abstracts.litellm.completion", mock_completion)

    cache_path = os.path.join(tmp_cache_dir, "abstract_summaries_cache.jsonl")
    result_df = summarize_too_long_abstracts(
        sample_df, model="test/model", cache_path=cache_path,
    )

    # too_long records should have abstract_status = "generated"
    long_mask = result_df["doi"].isin(["10.1000/long", "10.1000/long2"])
    assert (result_df.loc[long_mask, "abstract_status"] == "generated").all()

    # Their abstracts should be the summary
    for _, row in result_df[long_mask].iterrows():
        assert row["abstract"] == fake_summary

    # Normal records should have abstract_status = "original"
    normal_mask = result_df["doi"].isin(["10.1000/short", "10.1000/medium"])
    assert (result_df.loc[normal_mask, "abstract_status"] == "original").all()

    # Missing records should have abstract_status = "missing"
    missing_mask = result_df["doi"] == "10.1000/missing"
    assert (result_df.loc[missing_mask, "abstract_status"] == "missing").all()

    # Cache should contain 2 entries (the two long abstracts)
    cache = load_summary_cache(cache_path)
    assert len(cache) == 2


def test_cached_summaries_are_reused(monkeypatch, sample_df, tmp_cache_dir):
    """Pre-cached summaries skip LLM calls."""
    call_count = 0

    def mock_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        class Choice:
            class Message:
                content = "Fresh summary."
            message = Message()
        class Response:
            choices = [Choice()]
        return Response()

    monkeypatch.setattr("summarize_abstracts.litellm.completion", mock_completion)

    # Pre-populate cache for one of the two long abstracts
    cache_path = os.path.join(tmp_cache_dir, "abstract_summaries_cache.jsonl")
    pre_cache = {
        "10.1000/long": {"summary": "Cached summary.", "model": "test/model",
                          "tokens_original": 1500, "error": None},
    }
    save_summary_cache(pre_cache, cache_path)

    result_df = summarize_too_long_abstracts(
        sample_df, model="test/model", cache_path=cache_path,
    )

    # Only 1 LLM call (for long2), not 2
    assert call_count == 1

    # Cached abstract used as-is
    cached_row = result_df[result_df["doi"] == "10.1000/long"].iloc[0]
    assert cached_row["abstract"] == "Cached summary."
