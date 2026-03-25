"""Near-duplicate abstract detection for coordinated multi-journal publications.

Identifies clusters of papers with near-identical content (e.g., COP27
editorial published simultaneously in 62+ journals). Uses a two-pass approach:

  Pass 1 — **Abstract prefix clustering**: normalize abstracts (lowercase,
  strip non-alphanumeric), group by first N characters. Catches papers with
  identical or truncated abstracts.

  Pass 2 — **Title clustering with abstract validation**: normalize titles,
  group papers sharing the same title. Then verify the group is a true
  coordinated publication by checking abstract similarity (measured by
  pairwise normalized-prefix overlap). This prevents false positives from
  generic titles like "Editorial" or "Introduction".

  Union-find merges overlapping groups across both passes.

Strategy: flag, keep, and document. These are real publications — removing them
would be editorializing. But they should be identified for transparency.

Usage:
    from detect_near_duplicates import detect_near_duplicate_groups
    df["near_duplicate_group"] = detect_near_duplicate_groups(df)
"""

import re
from collections import defaultdict

import pandas as pd

from utils import get_logger

log = get_logger("detect_near_duplicates")

# Default parameters
DEFAULT_PREFIX_LENGTH = 200
DEFAULT_MIN_GROUP_SIZE = 5
DEFAULT_MIN_ABSTRACT_LENGTH = 50
# Fraction of papers in a title group that must share an abstract prefix
# with at least one other member for the group to be considered a true
# near-duplicate cluster (filters out generic titles with diverse content)
DEFAULT_ABSTRACT_OVERLAP_THRESHOLD = 0.5


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip non-alphanumeric, collapse spaces."""
    if not text or str(text) == "nan":
        return ""
    t = str(text).lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class _UnionFind:
    """Simple union-find to merge overlapping groups."""

    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def _abstract_overlap_ratio(abstracts: list[str], prefix_length: int) -> float:
    """Fraction of abstracts that share a normalized prefix with >= 1 other.

    Used to validate title-based groups: if abstracts are too diverse,
    the group is likely a false positive (e.g., generic "Editorial" title).
    """
    if len(abstracts) < 2:
        return 0.0

    prefixes = [_normalize_text(a)[:prefix_length] for a in abstracts]
    prefix_counts: dict[str, int] = defaultdict(int)
    for p in prefixes:
        if p:  # skip empty
            prefix_counts[p] += 1

    # Count abstracts whose prefix is shared with at least one other.
    # Empty/missing abstracts count AGAINST the ratio — a group of papers
    # sharing only a generic title (e.g., "References") with no abstracts
    # is not a near-duplicate cluster.
    shared = sum(1 for p in prefixes if p and prefix_counts[p] > 1)

    return shared / len(abstracts)


def detect_near_duplicate_groups(
    df: pd.DataFrame,
    *,
    prefix_length: int = DEFAULT_PREFIX_LENGTH,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
    min_abstract_length: int = DEFAULT_MIN_ABSTRACT_LENGTH,
    abstract_overlap_threshold: float = DEFAULT_ABSTRACT_OVERLAP_THRESHOLD,
) -> pd.Series:
    """Detect near-duplicate content clusters and return group assignments.

    Parameters
    ----------
    df : DataFrame
        Must contain 'abstract' and 'title' columns.
    prefix_length : int
        Number of characters (after normalization) to use for abstract grouping.
    min_group_size : int
        Minimum cluster size to flag as a near-duplicate group.
    min_abstract_length : int
        Minimum abstract length (raw) to consider for abstract-prefix pass.
    abstract_overlap_threshold : float
        For title-based groups, minimum fraction of members that must share
        an abstract prefix for the group to qualify. Set to 0 to disable
        abstract validation (pure title grouping).

    Returns
    -------
    pd.Series
        Named "near_duplicate_group". Contains integer group IDs for papers
        in near-duplicate clusters, pd.NA for all others.
    """
    result = pd.Series(pd.NA, index=df.index, dtype="Int64", name="near_duplicate_group")

    if len(df) == 0:
        return result

    uf = _UnionFind(len(df))
    idx_to_pos = {idx: pos for pos, idx in enumerate(df.index)}

    # ── Pass 1: Abstract prefix clustering ────────────────────────
    abstracts_raw = df["abstract"].fillna("").astype(str)
    has_abstract = abstracts_raw.str.len() >= min_abstract_length
    normalized_abstracts = abstracts_raw[has_abstract].apply(_normalize_text)
    abstract_prefixes = normalized_abstracts.str[:prefix_length]

    prefix_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, prefix in abstract_prefixes.items():
        if prefix:
            prefix_to_indices[prefix].append(idx)

    for prefix, indices in prefix_to_indices.items():
        if len(indices) >= min_group_size:
            anchor = idx_to_pos[indices[0]]
            for idx in indices[1:]:
                uf.union(anchor, idx_to_pos[idx])

    # ── Pass 2: Title clustering with abstract validation ─────────
    if "title" in df.columns:
        normalized_titles = df["title"].fillna("").apply(_normalize_text)

        title_to_indices: dict[str, list[int]] = defaultdict(list)
        for idx, title in normalized_titles.items():
            if title and len(title) >= 10:  # skip very short/empty titles
                title_to_indices[title].append(idx)

        for title, indices in title_to_indices.items():
            if len(indices) < min_group_size:
                continue

            # Validate: check abstract overlap within this title group
            group_abstracts = [str(abstracts_raw.at[i]) for i in indices]
            overlap = _abstract_overlap_ratio(group_abstracts, prefix_length)

            if overlap >= abstract_overlap_threshold:
                anchor = idx_to_pos[indices[0]]
                for idx in indices[1:]:
                    uf.union(anchor, idx_to_pos[idx])

    # ── Collect groups from union-find ────────────────────────────
    group_members: dict[int, list[int]] = defaultdict(list)
    for idx in df.index:
        root = uf.find(idx_to_pos[idx])
        group_members[root].append(idx)

    # Filter to groups meeting min_group_size and assign IDs
    group_id = 1
    groups_found = 0
    for root, members in sorted(group_members.items(), key=lambda x: -len(x[1])):
        if len(members) < min_group_size:
            continue
        for idx in members:
            result.loc[idx] = group_id
        groups_found += 1

        sample_title = df.loc[members[0], "title"] if "title" in df.columns else "?"
        log.info("  Group %d: %d records — %.60s",
                 group_id, len(members), str(sample_title)[:60])
        group_id += 1

    if groups_found > 0:
        log.info("Found %d near-duplicate groups (>= %d records each)",
                 groups_found, min_group_size)

    return result
