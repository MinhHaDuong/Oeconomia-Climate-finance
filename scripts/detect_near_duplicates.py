"""Near-duplicate abstract detection for coordinated multi-journal publications.

Identifies clusters of papers with near-identical abstracts (e.g., COP27
editorial published simultaneously in 62+ journals). Uses normalized abstract
prefix clustering: abstracts are lowercased, stripped of non-alphanumeric
characters, and grouped by their first N characters. Groups meeting a minimum
size threshold receive a shared group ID.

Strategy: flag, keep, and document. These are real publications — removing them
would be editorializing. But they should be identified for transparency.

Usage:
    from detect_near_duplicates import detect_near_duplicate_groups
    df["near_duplicate_group"] = detect_near_duplicate_groups(df)
"""

import re

import pandas as pd

from utils import get_logger

log = get_logger("detect_near_duplicates")

# Default parameters
DEFAULT_PREFIX_LENGTH = 200
DEFAULT_MIN_GROUP_SIZE = 5
DEFAULT_MIN_ABSTRACT_LENGTH = 50


def _normalize_abstract(text: str) -> str:
    """Normalize abstract text for comparison.

    Lowercase, strip non-alphanumeric characters (except spaces),
    collapse whitespace. This handles punctuation variants (Oxford comma,
    em-dashes) and minor wording differences.
    """
    if not text:
        return ""
    t = str(text).lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def detect_near_duplicate_groups(
    df: pd.DataFrame,
    *,
    prefix_length: int = DEFAULT_PREFIX_LENGTH,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
    min_abstract_length: int = DEFAULT_MIN_ABSTRACT_LENGTH,
) -> pd.Series:
    """Detect near-duplicate abstract clusters and return group assignments.

    Parameters
    ----------
    df : DataFrame
        Must contain an 'abstract' column.
    prefix_length : int
        Number of characters (after normalization) to use for grouping.
    min_group_size : int
        Minimum cluster size to flag as a near-duplicate group.
    min_abstract_length : int
        Minimum abstract length (raw) to consider. Shorter abstracts are
        excluded to avoid false positives from boilerplate stubs.

    Returns
    -------
    pd.Series
        Named "near_duplicate_group". Contains integer group IDs for papers
        in near-duplicate clusters, pd.NA for all others.
    """
    result = pd.Series(pd.NA, index=df.index, dtype="Int64", name="near_duplicate_group")

    if len(df) == 0:
        return result

    # Filter to papers with substantive abstracts
    abstracts = df["abstract"].fillna("").astype(str)
    has_abstract = abstracts.str.len() >= min_abstract_length

    # Normalize and take prefix
    normalized = abstracts[has_abstract].apply(_normalize_abstract)
    prefixes = normalized.str[:prefix_length]

    # Group by prefix, find clusters meeting min_group_size
    prefix_counts = prefixes.value_counts()
    large_groups = prefix_counts[prefix_counts >= min_group_size]

    if large_groups.empty:
        return result

    log.info("Found %d near-duplicate groups (>= %d records each)",
             len(large_groups), min_group_size)

    # Assign group IDs
    group_id = 1
    for prefix, count in large_groups.items():
        mask = prefixes == prefix
        indices = prefixes[mask].index
        result.loc[indices] = group_id
        # Log first occurrence for transparency
        sample_title = df.loc[indices[0], "title"] if "title" in df.columns else "?"
        log.info("  Group %d: %d records — %.60s…", group_id, count,
                 str(sample_title)[:60])
        group_id += 1

    return result
