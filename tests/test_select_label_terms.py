"""Regression test: re-calling _select_label_terms after merge produces
the same result as the old _fill_remaining_slots.

The second pass of _select_label_terms replaced a separate _fill_remaining_slots
function.  This test verifies behavioral equivalence on synthetic candidates.

Functions are copied here to avoid importing compute_clusters.py (which pulls
in numpy/sklearn). If the originals change, this test should be updated.
"""


# --- Copied from compute_clusters.py (pure Python, no numpy) ---

def _word_count(terms):
    return sum(len(t.split()) for t in terms)


def _select_label_terms(candidates, promoted, max_words, scored, used_tokens):
    """Select label terms prioritizing promoted bigrams, respecting word budget."""
    # Promoted bigrams first
    for term, _ in candidates:
        if term not in promoted:
            continue
        if _word_count(scored) + len(term.split()) > max_words:
            continue
        tokens = set(term.split())
        stems = {t.rstrip("s") for t in tokens}
        used_stems = {t.rstrip("s") for t in used_tokens}
        if stems.issubset(used_stems):
            continue
        scored.append(term)
        used_tokens.update(tokens)
        if _word_count(scored) >= max_words:
            break
    # Non-promoted fill
    for term, _ in candidates:
        if _word_count(scored) >= max_words:
            break
        if " " in term and term not in promoted:
            continue
        if _word_count(scored) + len(term.split()) > max_words:
            continue
        tokens = set(term.split())
        if tokens.issubset(used_tokens):
            continue
        stems = {t.rstrip("s") for t in tokens}
        used_stems = {t.rstrip("s") for t in used_tokens}
        if stems.issubset(used_stems):
            continue
        scored.append(term)
        used_tokens.update(tokens)
    return scored, used_tokens


def _merge_unigram_pairs(scored, used_tokens, bigram_dist, unigram_dist):
    """Merge adjacent unigram pairs into bigrams where stronger."""
    merged_flag = True
    while merged_flag:
        merged_flag = False
        for i, a in enumerate(scored):
            if " " in a:
                continue
            for j, b in enumerate(scored):
                if j <= i or " " in b:
                    continue
                for bigram in (f"{a} {b}", f"{b} {a}"):
                    if bigram not in bigram_dist:
                        continue
                    weaker = min(unigram_dist.get(a, 0), unigram_dist.get(b, 0))
                    if bigram_dist[bigram] >= weaker:
                        scored[i] = bigram
                        scored.pop(j)
                        used_tokens.update(bigram.split())
                        merged_flag = True
                        break
                if merged_flag:
                    break
            if merged_flag:
                break
    return scored, used_tokens


# --- Old function, preserved for comparison ---

def _old_fill_remaining_slots(scored, used_tokens, candidates, promoted, max_words):
    """Original _fill_remaining_slots, preserved verbatim for comparison."""
    for term, _ in candidates:
        if _word_count(scored) >= max_words:
            break
        if _word_count(scored) + len(term.split()) > max_words:
            continue
        tokens = set(term.split())
        if tokens.issubset(used_tokens):
            continue
        stems = {t.rstrip("s") for t in tokens}
        used_stems = {t.rstrip("s") for t in used_tokens}
        if stems.issubset(used_stems):
            continue
        if " " in term and term not in promoted:
            continue
        scored.append(term)
        used_tokens.update(tokens)


# --- Test data ---

CANDIDATES = [
    ("green bond", 0.12),
    ("carbon pricing", 0.10),
    ("debt swap", 0.08),
    ("renewable energy", 0.07),
    ("bond", 0.11),
    ("pricing", 0.09),
    ("green", 0.085),
    ("debt", 0.075),
    ("renewable", 0.065),
    ("swap", 0.06),
    ("energy", 0.055),
    ("transition", 0.05),
    ("taxonomy", 0.04),
    ("sovereign", 0.035),
    ("blended", 0.03),
]

PROMOTED = {"green bond", "carbon pricing", "debt swap"}

BIGRAM_DIST = {
    "green bond": 0.12,
    "carbon pricing": 0.10,
    "debt swap": 0.08,
    "renewable energy": 0.07,
    "bond pricing": 0.04,
}
UNIGRAM_DIST = {
    "bond": 0.11,
    "pricing": 0.09,
    "green": 0.085,
    "debt": 0.075,
    "renewable": 0.065,
    "swap": 0.06,
    "energy": 0.055,
    "transition": 0.05,
    "taxonomy": 0.04,
    "sovereign": 0.035,
    "blended": 0.03,
}


def _run_old_pipeline(candidates, promoted, max_words):
    """Original 3-step: select → merge → fill_remaining_slots."""
    scored, used_tokens = _select_label_terms(
        candidates, promoted, max_words, [], set()
    )
    scored, used_tokens = _merge_unigram_pairs(
        scored, used_tokens, BIGRAM_DIST, UNIGRAM_DIST
    )
    _old_fill_remaining_slots(scored, used_tokens, candidates, promoted, max_words)
    return scored


def _run_new_pipeline(candidates, promoted, max_words):
    """New pipeline: select → merge → re-select."""
    scored, used_tokens = _select_label_terms(
        candidates, promoted, max_words, [], set()
    )
    scored, used_tokens = _merge_unigram_pairs(
        scored, used_tokens, BIGRAM_DIST, UNIGRAM_DIST
    )
    scored, used_tokens = _select_label_terms(
        candidates, promoted, max_words, scored, used_tokens
    )
    return scored


class TestSelectLabelTermsReuse:
    """Verify that calling _select_label_terms twice matches old fill behavior."""

    def test_equivalence_standard(self):
        assert _run_old_pipeline(CANDIDATES, PROMOTED, 10) == \
               _run_new_pipeline(CANDIDATES, PROMOTED, 10)

    def test_equivalence_tight_budget(self):
        assert _run_old_pipeline(CANDIDATES, PROMOTED, 4) == \
               _run_new_pipeline(CANDIDATES, PROMOTED, 4)

    def test_equivalence_generous_budget(self):
        assert _run_old_pipeline(CANDIDATES, PROMOTED, 20) == \
               _run_new_pipeline(CANDIDATES, PROMOTED, 20)

    def test_equivalence_no_promoted(self):
        assert _run_old_pipeline(CANDIDATES, set(), 10) == \
               _run_new_pipeline(CANDIDATES, set(), 10)

    def test_equivalence_all_promoted(self):
        all_bigrams = {t for t, _ in CANDIDATES if " " in t}
        assert _run_old_pipeline(CANDIDATES, all_bigrams, 10) == \
               _run_new_pipeline(CANDIDATES, all_bigrams, 10)

    def test_reselect_adds_nothing_when_budget_full(self):
        """When budget is already full, re-calling doesn't change anything."""
        scored, used = _select_label_terms(CANDIDATES, PROMOTED, 6, [], set())
        scored_copy = list(scored)
        scored, used = _select_label_terms(CANDIDATES, PROMOTED, 6, scored, used)
        assert scored == scored_copy
