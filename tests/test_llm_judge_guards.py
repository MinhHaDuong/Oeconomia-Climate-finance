"""Tests for the LLM-judge reduction guards (ticket 0148).

Red-first: each guard is exercised on a faithful reduction (passes) and on a
known-bad reduction (trips the specific guard).

No pytest marker: these are pure unit tests (no subprocess, no I/O), so they run
in the default `check-fast` bucket — unlike the `adherence`-marked governance
tests in test_editorial_governance.py.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from qa_llm_judge_guards import (
    check_reduction,
    count_em_dashes,
    extract_numbers,
    introduced_llmisms,
    invented_numbers,
    load_llmisms,
    word_count,
)

LLMISMS = ["delve", "tapestry", "robust"]
REPO_ROOT = Path(__file__).resolve().parent.parent


def test_word_count():
    assert word_count("the quick brown fox") == 4
    assert word_count("") == 0


def test_count_em_dashes():
    # Literal U+2014 plus the Markdown --- ligature.
    assert count_em_dashes("a — b --- c") == 2
    assert count_em_dashes("no dashes here") == 0


def test_extract_numbers():
    nums = extract_numbers("In 2009, $100 billion was pledged; 2.5% of GDP.")
    assert "2009" in nums
    assert "100" in nums
    assert "2.5" in nums


def test_invented_numbers_flags_fabrication():
    src = "The Copenhagen pledge was $100 billion in 2009."
    bad = "The pledge was $300 billion in 2009."  # 300 invented
    assert "300" in invented_numbers(src, bad)
    # A faithful reduction invents nothing.
    good = "A $100 billion pledge in 2009."
    assert invented_numbers(src, good) == []


def test_introduced_llmisms_flags_tells():
    assert "delve" in introduced_llmisms("Let us delve into the data.", LLMISMS)
    assert introduced_llmisms("A plain factual sentence.", LLMISMS) == []


def test_check_reduction_passes_faithful():
    src = "Economists built the accounting categories of climate finance after 2009."
    reduced = "Economists built climate-finance accounting categories after 2009."
    report = check_reduction(src, reduced, LLMISMS)
    assert report.ok
    assert report.word_reduction_ok
    assert report.em_dash_ok
    assert report.invented_numbers == []
    assert report.introduced_llmisms == []


def test_check_reduction_catches_growth():
    src = "Short source sentence."
    reduced = "A much longer reduced output that has clearly grown well beyond its source."
    report = check_reduction(src, reduced, LLMISMS)
    assert not report.ok
    assert not report.word_reduction_ok


def test_check_reduction_catches_em_dash():
    src = "Economists built the categories after the Copenhagen pledge in 2009."
    reduced = "Economists built the categories — after Copenhagen 2009."
    report = check_reduction(src, reduced, LLMISMS)
    assert not report.ok
    assert not report.em_dash_ok


def test_check_reduction_catches_invented_number_and_verdict():
    src = "Economists built the categories after the Copenhagen pledge in 2009."
    reduced = "Economists built robust categories after the 2015 pledge."
    report = check_reduction(src, reduced, LLMISMS)
    assert not report.ok
    assert "2015" in report.invented_numbers
    assert "robust" in report.introduced_llmisms


def test_cli_has_argparse():
    """CLI flag presence by source inspection (project rule)."""
    src = (REPO_ROOT / "scripts" / "qa_llm_judge_guards.py").read_text(encoding="utf-8")
    assert "argparse" in src
    assert "--input" in src
    assert "--reduced" in src


def test_load_llmisms_against_real_config():
    """Guard against ai-tells.yml schema drift silently emptying the wordlist."""
    words = load_llmisms(REPO_ROOT / "config" / "ai-tells.yml")
    assert "delve" in words  # a blacklisted word
    assert "robust" in words  # a conditional word, folded in unconditionally
