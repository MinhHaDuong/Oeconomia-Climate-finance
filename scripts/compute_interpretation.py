"""Compute discriminative terms for a transition zone (ticket 0056).

For a given zone (year range), computes log-odds ratios with Dirichlet prior
(Monroe et al. 2008) comparing term frequencies before-zone vs after-zone.
This answers: *what* changed at each validated transition zone?

Usage:
    uv run python scripts/compute_interpretation.py --zone 2007-2011 \
        --output content/tables/tab_interp_2007_2011.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        uv run python scripts/compute_interpretation.py --zone 2007-2011 \
        --output /tmp/tab_interp_2007_2011.csv
"""

import argparse
import re
from collections import Counter

import numpy as np
import pandas as pd
from pipeline_loaders import load_analysis_config, load_refined_works
from schemas import InterpretationSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_interpretation")

# Default number of top terms to report
DEFAULT_TOP_N = 50


# ---------------------------------------------------------------------------
# Core: log-odds ratio with Dirichlet prior (Monroe et al. 2008)
# ---------------------------------------------------------------------------


def _tokenize(texts):
    """Simple whitespace + lowercase tokenization with stopword removal.

    Returns a list of token lists.
    """
    # Minimal English stopwords (sklearn's list is large; keep it simple)
    stopwords = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "not",
        "no",
        "as",
        "if",
        "than",
        "so",
        "such",
        "about",
        "between",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "any",
        "only",
        "own",
        "same",
        "very",
        "just",
        "also",
        "into",
        "which",
        "what",
        "who",
        "whom",
        "while",
        "we",
        "they",
        "he",
        "she",
        "her",
        "his",
    }
    result = []
    for text in texts:
        tokens = re.findall(r"[a-z]+", text.lower())
        tokens = [t for t in tokens if t not in stopwords and len(t) > 2]
        result.append(tokens)
    return result


def log_odds_ratio(texts_before, texts_after, top_n=DEFAULT_TOP_N):
    """Compute log-odds ratios with Dirichlet prior (Monroe et al. 2008).

    Parameters
    ----------
    texts_before : list[str]
        Abstracts from the before-zone period.
    texts_after : list[str]
        Abstracts from the after-zone period.
    top_n : int
        Number of top discriminative terms to return (by |log_odds|).

    Returns
    -------
    pd.DataFrame
        Columns: term, log_odds, freq_before, freq_after.
        Sorted by |log_odds| descending.

    Raises
    ------
    ValueError
        If either text list is empty.

    """
    if not texts_before:
        raise ValueError("texts_before is empty")
    if not texts_after:
        raise ValueError("texts_after is empty")

    tokens_before = _tokenize(texts_before)
    tokens_after = _tokenize(texts_after)

    # Count term frequencies
    freq_before = Counter()
    for doc_tokens in tokens_before:
        freq_before.update(doc_tokens)

    freq_after = Counter()
    for doc_tokens in tokens_after:
        freq_after.update(doc_tokens)

    # Combined vocabulary
    vocab = set(freq_before.keys()) | set(freq_after.keys())
    if not vocab:
        return pd.DataFrame(columns=["term", "log_odds", "freq_before", "freq_after"])

    # Total tokens in each period
    n_before = sum(freq_before.values())
    n_after = sum(freq_after.values())

    # Dirichlet prior: use overall corpus frequency as informative prior
    freq_total = Counter()
    for term in vocab:
        freq_total[term] = freq_before[term] + freq_after[term]
    n_total = n_before + n_after

    # Alpha: informative prior proportional to overall frequency
    # alpha_w = freq_total[w] / n_total  (normalized to sum to 1)
    # Scaled by vocabulary size to control prior strength
    alpha_0 = len(vocab)  # total prior mass

    rows = []
    for term in vocab:
        f_b = freq_before[term]
        f_a = freq_after[term]
        alpha_w = alpha_0 * (freq_total[term] / n_total)

        # Log-odds ratio with Dirichlet prior
        # log( (f_a + alpha_w) / (n_after + alpha_0 - f_a - alpha_w) )
        # - log( (f_b + alpha_w) / (n_before + alpha_0 - f_b - alpha_w) )
        log_odds_after = np.log((f_a + alpha_w) / (n_after + alpha_0 - f_a - alpha_w))
        log_odds_before = np.log((f_b + alpha_w) / (n_before + alpha_0 - f_b - alpha_w))
        lo = log_odds_after - log_odds_before

        rows.append(
            {
                "term": term,
                "log_odds": float(lo),
                "freq_before": f_b,
                "freq_after": f_a,
            }
        )

    df = pd.DataFrame(rows)
    df["abs_log_odds"] = df["log_odds"].abs()
    df = df.sort_values("abs_log_odds", ascending=False).head(top_n)
    df = df.drop(columns=["abs_log_odds"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zone",
        required=True,
        help="Transition zone as 'START-END' (e.g., '2007-2011')",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Number of top discriminative terms (default: {DEFAULT_TOP_N})",
    )
    args = parser.parse_args(extra)

    # Parse zone
    match = re.match(r"^(\d{4})-(\d{4})$", args.zone)
    if not match:
        raise ValueError(f"Invalid zone format: '{args.zone}'. Expected 'YYYY-YYYY'.")
    zone_start = int(match.group(1))
    zone_end = int(match.group(2))
    if zone_start >= zone_end:
        raise ValueError(
            f"Zone start ({zone_start}) must be before zone end ({zone_end})."
        )

    log.info("=== Interpretation: zone %d-%d ===", zone_start, zone_end)

    # Load corpus
    cfg = load_analysis_config()
    year_min = cfg["periodization"]["year_min"]
    year_max = cfg["periodization"]["year_max"]

    works = load_refined_works()
    works["year"] = pd.to_numeric(works["year"], errors="coerce")

    # Filter to works with abstracts
    has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 0)
    in_range = (works["year"] >= year_min) & (works["year"] <= year_max)
    works = works[has_abstract & in_range].copy()

    # Split into before-zone and after-zone
    before_mask = works["year"] < zone_start
    after_mask = works["year"] > zone_end
    texts_before = works.loc[before_mask, "abstract"].tolist()
    texts_after = works.loc[after_mask, "abstract"].tolist()

    log.info(
        "Before zone (<=%d): %d documents, After zone (>=%d): %d documents",
        zone_start - 1,
        len(texts_before),
        zone_end + 1,
        len(texts_after),
    )

    if not texts_before or not texts_after:
        log.warning(
            "Insufficient documents for zone %d-%d "
            "(before=%d, after=%d). Writing empty output.",
            zone_start,
            zone_end,
            len(texts_before),
            len(texts_after),
        )
        result = pd.DataFrame(columns=["term", "log_odds", "freq_before", "freq_after"])
    else:
        result = log_odds_ratio(texts_before, texts_after, top_n=args.top_n)

    # Validate and save
    InterpretationSchema.validate(result)
    result.to_csv(io_args.output, index=False)
    log.info("Saved %d terms -> %s", len(result), io_args.output)


if __name__ == "__main__":
    main()
