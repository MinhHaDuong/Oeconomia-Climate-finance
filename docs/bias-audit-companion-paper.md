# Bias audit — companion paper (QSS submission)

Date: 2026-04-17
Ticket: 0070
Status: pre-submission due diligence, feeds §4.8 Robustness + §6.4 Limitations
  rewrite under ticket 0057.

## How to read this document

Each bias below follows the same schema:

1. **Description** — one or two paragraphs.
2. **Affected methods** — which of the six divergence channels (S2 cosine,
   L1 JS, G2 spectral, G9 community, plus the bimodality and censored-gap
   variants) the bias can distort.
3. **Current defense** — script or config anchor, with line number, plus
   the ticket(s) that established it.
4. **Status** — one of:
   - ✅ **fixed in pipeline** — a mechanism exists and is on by default.
   - ⚠ **mitigated** — partial defense; reviewer can still push back.
   - ℹ **limitation** — acknowledged in §6.4; no defense attempted.
   - ❌ **gap** — no defense; a child ticket is open.
5. **Recommended action** — only populated when status is ⚠ or ❌.

A reviewer should be able to take any B-code and get a one-sentence honest
defense. When no such defense is possible we prefer explicit ❌ + ticket
over silent hope.

## Summary table

| ID  | Bias                                  | Affects                | Status | Child ticket |
|-----|---------------------------------------|------------------------|--------|--------------|
| B1  | Organic corpus size growth            | all channels           | ✅     | —            |
| B2  | Retro-indexing of pre-DOI era         | all channels (pre-2005)| ❌     | 0071         |
| B3  | English-language dominance            | S2, L1                 | ⚠      | 0072         |
| B4  | Editorial cartel / venue concentration| L1, G2, G9             | ❌     | 0073         |
| B5  | Citation threshold ≥ 50 (core subset) | core-subset claims     | ℹ      | —            |
| B6  | Louvain partition stochasticity       | G9                     | ⚠      | 0074         |
| B7  | Window size arbitrariness (w)         | all channels           | ⚠      | 0075         |
| B8  | Multiple comparisons                  | transition-zone claims | ⚠      | 0076         |
| B9  | Permutation exchangeability           | null p-values          | ✅     | —            |
| B10 | DOI resolution rate varies by era     | G2, G9                 | ❌     | 0077         |
| B11 | Embedding model choice (BGE-M3)       | S2 and all embedding   | ℹ      | 0036 (open)  |
| B12 | Data snapshot cutoff                  | post-2023 slice        | ⚠      | 0067 (open)  |
| B13 | Config/paper window mismatch          | paper §6.4 prose       | ⚠      | 0075 (w/ B7) |

## Data-generating biases

### B1. Organic corpus size growth ✅

**Description.** Papers per year grows roughly exponentially over
1998–2024. Any distributional statistic computed on a larger sample has
smaller sampling variance, so an apparent "divergence" is partly a
sample-size artifact. This was the original failure mode that surfaced
the growth-bias correction work.

**Affected.** Every divergence channel (S1–S4, L1–L3, G1–G9).

**Current defense.**
- Equal-n subsampling: `config/analysis.yaml:29` sets `equal_n: true`.
  The divergence pipeline subsamples both windows down to
  `min(n_before, n_after)` before computing the statistic
  (`scripts/_divergence_semantic.py:134`, `scripts/_divergence_lexical.py`,
  `scripts/_divergence_io.py::subsample_equal_n`).
- Permutation null: `scripts/compute_null_model.py::permutation_test`
  (line 40–80) runs 500 permutations (`n_perm: 500`, `config:35`) and
  reports the Z-score of the observed statistic against the null.
- Ticket 0045 closed 2026-04-16 established both mechanisms and verified
  that the monotone-declining trend artifact disappears.

**Recommended action.** None. A reviewer asking "is the divergence a
sample-size artifact?" gets a one-liner: equal-n + permutation null,
both on by default, reference ticket 0045.

### B2. Retro-indexing of pre-DOI era ❌

**Description.** OpenAlex and similar sources add pre-2000 records as
third-party metadata improves. A 1995 slice of the corpus queried in 2026
differs from what a 1995 slice would have looked like if queried in 1995
(or even 2010). If indexing is skewed toward post-hoc additions of old
papers, the pre-2005 window is systematically different from the
post-2005 window in ways that have nothing to do with field structure.

**Affected.** All channels on the pre-2005 tail. Because our
periodization places Act I at 1990–2006, this bias sits directly inside
the evidence base for the "before climate finance" narrative.

**Current defense.** None detected. `scripts/enrich_*.py` and
`scripts/corpus_*.py` do not use `indexed_date` or `created_at` against
`publication_year`. No config flag exists.

**Recommended action.** Open child ticket (see §"Child tickets" below).
Characterize the indexing-year skew; if the skew is material, add a
"record-age-window" filter (e.g., include only records first indexed
before `publication_year + N` years) and re-run the pre-2005 slice. At
minimum, add a §4.8 paragraph acknowledging the issue with a back-of-the-
envelope estimate of its magnitude.

### B3. English-language dominance ⚠

**Description.** Corpus is multilingual but skews English. BGE-M3 embeds
all languages into a shared 1024-d space, but the shared space is trained
on predominantly English and Chinese web text. Representation quality is
uneven across languages, which can bias cosine and JS toward or away from
structural similarity that is really language-similarity.

**Affected.** S2 (semantic cosine) and L1 (lexical JS). Less material for
graph channels (G2, G9) since citation edges are language-agnostic once
DOIs resolve.

**Current defense.**
- Embedding model: `scripts/enrich_embeddings.py:36` uses `BAAI/bge-m3`
  explicitly for multilingual coverage of English, French, Chinese,
  Japanese, German (`content/_includes/embedding-generation.md:5`).
- §6.4 already acknowledges: "We use `BAAI/bge-m3`, a multilingual
  model... future work should compare results across embedding models."
- Language enrichment pipeline (`scripts/enrich_language.py`) assigns a
  language label per record, so the data is available for stratification.

**Recommended action.** ⚠ — the defense addresses model choice but not
language stratification. Open a child ticket to run S2 and L1 on the
English-only subset and report whether transition zones shift. If zones
are stable, the multilingual claim holds. If they shift, §4.8 needs a
paragraph qualifying the claim.

### B4. Editorial cartel / venue concentration ❌

**Description.** A small number of journals publish a large fraction of
climate-finance papers (Climate Policy, Climatic Change, Nature Climate
Change, WIREs Climate Change, Journal of Sustainable Finance &
Investment). Editors, reviewers, and author networks concentrate within
venues. A "structural break" might reflect an editorial taste shift or a
special-issue pulse, not field-level change.

**Affected.** L1 (lexical, since venue style correlates with vocabulary),
G2 (spectral, since in-venue co-citation is dense), and G9 (community
partition, since communities often track venues).

**Current defense.** None detected. `scripts/summarize_core_venues.py`
produces a post-hoc summary but is not part of the analysis pipeline. No
venue-concentration index (Herfindahl, entropy, HHI) is computed per
year.

**Recommended action.** Open child ticket. Compute venue-concentration
per year and report whether the 2007 and 2013 transition zones coincide
with concentration shocks. Minimum deliverable: a supplementary figure of
Herfindahl or Shannon entropy of venue share by year, overlaid with the
detected breakpoints.

## Method-specific biases

### B5. Citation threshold for core subset (cited_by_count ≥ 50) ℹ

**Description.** Core subset is defined by `cited_by_count ≥ 50`
(`config/analysis.yaml:12`). Recent papers
haven't had time to accumulate citations, so the core is systematically
older than the full corpus. The "no break in core" finding is partly a
recency-floor artifact: 2022–2024 papers are under-represented.

**Affected.** All core-subset claims, including the headline "no
structural break in the core" result.

**Current defense.** `content/companion-paper.qmd:209` already
acknowledges: "The core subset is defined by cited_by_count ≥ 50, a
conventional threshold that creates recency bias... The 2023 boundary
artifact in the core analysis is a direct consequence of this bias."

**Recommended action.** ℹ — limitation is already stated. We can
strengthen it with a quantitative line in §6.4: share of 2020+ papers
that cleared the threshold as of the snapshot date. This is cheap;
absorb into ticket 0057 rewrite rather than a separate ticket.

### B6. Louvain community partition stochasticity ⚠

**Description.** G9 community divergence depends on a Louvain partition,
which is seed-dependent. A different random seed can reassign nodes to
different communities and thus produce a different Jensen-Shannon
divergence between windows. If the Z-score is unstable across seeds, G9
is an unreliable signal.

**Affected.** G9 only.

**Current defense.**
- Seed is read from config: `scripts/_divergence_community.py:32` reads
  `config/analysis.yaml:23` (`random_seed: 42`).
- Union-graph trick: the pipeline builds a single graph union of both
  windows' nodes and internal edges, then runs Louvain once on the
  union, so both windows share a partition
  (`scripts/_divergence_community.py:53–60, 79–80`).
- Ticket 0061 (closed) fixed shared-RNG contamination between
  permutation and subsampling paths, so the seed is now honored.

**Recommended action.** ⚠ — mechanism exists but across-seed variance is
not reported. Open a child ticket to sweep the seed (e.g., 10
realizations), report mean and standard deviation of G9 Z-score at each
candidate breakpoint, and print it next to the point estimate in §4.8. If
SD is small relative to the Z > 2 threshold, G9 is robust; if SD is
comparable to the signal, §6.4 needs a caveat.

### B7. Window size arbitrariness (w ∈ {2,3,4,5}) ⚠

**Description.** The paper reports a lead result at w = 3 with
sensitivity across w ∈ {2,3,4}. The question is whether 3 years is the
right temporal resolution — too small and year-to-year noise dominates;
too large and a real break gets smeared.

**Affected.** All channels, but especially the cosine/JS single-year
peaks.

**Current defense.**
- Config allows `windows: [2, 3, 4, 5]` (`config/analysis.yaml:25`).
- The "≥ 2 of 3 windows" robustness rule is implemented in
  `scripts/compute_breakpoints.py:140–165` (`find_robust_breakpoints`).
- Companion paper §6.4 states "Results are tested with half-widths w = 2,
  3, 4" (`content/companion-paper.qmd:211`).

**Recommended action.** ⚠ — two issues:

1. **Config/paper mismatch.** Config has `[2, 3, 4, 5]` but §6.4 says
   `{2, 3, 4}`. Either the paper is wrong (w = 5 results exist and are
   not reported) or the config is ambitious (w = 5 is declared but not
   used). Must be reconciled before submission.
2. **Lead window rationale.** Why w = 3? §4.8 should state the criterion
   explicitly (smallest window with stable peaks across realizations, or
   similar).

Open child ticket.

### B8. Multiple comparisons ⚠

**Description.** Six methods × ~22 years × 4 window widths ≈ 528
pointwise tests. At α = 0.05 pointwise, the expectation under the
global null is ≈ 26 false-positive year-method pairs. Any given
transition zone sits inside this haystack.

**Affected.** Every transition-zone claim, especially the 2007 and 2013
dates cited in the abstract.

**Current defense.** Multi-signal validation (≥ 2 independent channels
above Z > 2.0 within a 2-year window), implemented as the "≥ 2 of 3
windows" vote in `scripts/compute_breakpoints.py:160` and reinforced by
a cross-channel agreement rule described in the paper at line 132
("detected in 2 of 3 window sizes"). This is a correction-by-design but
not a formal Type-I-error statement.

**Recommended action.** ⚠ — formalize. Open a child ticket to compute a
meta-null: run all six methods on the permuted-labels corpus (500
realizations) and report the empirical probability that ≥ 2 channels
jointly exceed Z > 2 at the same year under the global null. That single
number is the joint Type I error for a validated transition zone; cite
it in §4.8. Likely small (< 0.01) but worth proving rather than
asserting.

### B9. Permutation test exchangeability assumption ✅

**Description.** The permutation null shuffles before/after labels within
a local pool. This is valid iff the two halves are exchangeable under H0,
i.e., drawn from the same distribution with the only difference being
the label. If B1 (growth) or B2 (retro-indexing) makes the two halves
structurally asymmetric even under H0, the permutation null underestimates
variance and inflates Type I error.

**Affected.** Every p-value and Z-score derived from the permutation null.

**Current defense.** Equal-n subsampling
(`config/analysis.yaml:29 equal_n: true`) removes the sample-size asymmetry
that is the main exchangeability violator. The permutation shuffles the
equal-sized pooled sample (`scripts/compute_null_model.py:70`), so under
equal-n the exchangeability assumption is close to satisfied. B1 is thus
handled for the null as well as for the point estimate.

**Recommended action.** None beyond B2. Retro-indexing is the residual
threat to exchangeability; its handling is tracked under B2.

### B10. DOI resolution rate varies by era ❌

**Description.** Citation-graph edges require both source and target DOIs
to resolve to corpus works. Pre-2000 DOI coverage is incomplete; 2000–2010
better; 2010+ nearly complete. The internal citation-graph density per
year therefore varies by era in a way orthogonal to field structure, and
a "spectral" or "community" break can reflect a density step-change
rather than a real structural discontinuity.

**Affected.** G2 (spectral) and G9 (community). S-methods and L-methods
are unaffected.

**Current defense.** Sliding windows partly normalize within-window
density variation, but the cross-window comparison is not density-
controlled.

**Recommended action.** Open child ticket. Report edge-density per year
of the internal citation graph (edges / node²) and flag any year whose
density is more than 2 SD from the local mean. If a detected transition
zone coincides with a density step-change, qualify the claim in §6.4.

### B11. Embedding model choice (BAAI/bge-m3) ℹ

**Description.** BGE-M3 is a multilingual 1024-d model trained on web
text. Domain-specific models (SciBERT, ClimateBERT, SPECTER2) might give
different cluster structures and thus different breakpoints.

**Affected.** S1–S4 and any channel that depends on cluster assignments
(L3 bursts in part).

**Current defense.** `content/companion-paper.qmd:205` explicitly
acknowledges: "Domain-specific models (SciBERT, ClimateBERT) might
produce different cluster structures. The framework's robustness to
model choice has not been tested; future work should compare results
across embedding models." Ticket 0036 (open) is the future-work handle.

**Recommended action.** None for this submission. Ticket 0036 tracks the
follow-up.

## Meta

### B12. Data cutoff / snapshot date ⚠

**Description.** The corpus snapshot was taken on a specific date
(~2026-03-26 per the Zenodo release directory). Papers published after
that date but with `publication_year ≤ 2024` are excluded, and 2024–2025
are systematically incomplete. The tail of every time series is biased
down.

**Affected.** All post-2023 claims.

**Current defense.**
- Year range enforced: `config/analysis.yaml:6–7`
  (`year_min: 1990`, `year_max: 2024`).
- Ticket 0067 (open) addresses per-window year bounds so the rolling
  window does not compute a divergence on a truncated tail.
- README.md title mentions 1990–2024.

**Recommended action.** ⚠ — two follow-ups:

1. Close ticket 0067 before submission.
2. Document the exact snapshot date explicitly in §3.1 Data and in the
   data availability statement. One sentence: "The corpus snapshot used
   in this paper was taken on YYYY-MM-DD. Records with publication_year
   2024 or earlier but first indexed after this date are excluded."

## Biases surfaced during the audit

### B13. Config/paper window mismatch (documentation bias) ⚠

Not a statistical bias in the data, but a defensible-paper bias. The
config declares `windows: [2, 3, 4, 5]` but §6.4 reports results "tested
with half-widths w = 2, 3, 4". A reviewer will ask what happened to
w = 5. Folded into ticket 0075 (B7); no separate child ticket.

## Child tickets to open

| Child    | Parent bias | Title                                              |
|----------|-------------|----------------------------------------------------|
| 0071     | B2          | Characterize retro-indexing skew (indexed vs pub year) |
| 0072     | B3          | Language-stratified S2/L1 sensitivity (English-only subset) |
| 0073     | B4          | Venue concentration (Herfindahl/entropy) per year  |
| 0074     | B6          | Across-seed Louvain variance for G9 Z-scores       |
| 0075     | B7          | Reconcile window set; state lead-window rationale  |
| 0076     | B8          | Joint Type I error for validated transition zones  |
| 0077     | B10         | Citation-graph edge density per year               |
| 0078     | B12         | Document snapshot date in §3.1 and data statement  |

Each child ticket lists the parent B-code and the minimum deliverable
needed to either close the gap or to produce a paragraph for §4.8.

## Feeding §4.8 Robustness and §6.4 Limitations

§4.8 Robustness is currently missing from `content/companion-paper.qmd`
(sections jump from 4.5 to 5). Ticket 0057 will add it. The audit
recommends §4.8 contain, at minimum:

1. One paragraph on equal-n + permutation null (from B1/B9).
2. One paragraph on window sensitivity and the ≥ 2-of-3 rule (from B7).
3. One paragraph on Louvain across-seed variance (from B6).
4. One paragraph on multi-signal validation with the joint Type I error
   number (from B8).

§6.4 Limitations should keep its current five items and add:

5. Retro-indexing (B2) — one sentence.
6. Venue concentration (B4) — one sentence.
7. Citation-graph density by era (B10) — one sentence.
8. Language-stratified sensitivity (B3) — one sentence if gaps remain
   after child ticket 0072 runs.

## Re-audit checklist before submission

- [ ] All child tickets 0071–0078 either closed or explicitly acknowledged
      in §6.4.
- [ ] §4.8 present and covers B1, B6, B7, B8.
- [ ] §6.4 covers B2, B3 (if 0072 yields gaps), B4, B5, B10, B11, B12.
- [ ] Snapshot date documented in §3.1 and in the data-availability
      statement.
- [ ] This document attached as a submission supplementary (if QSS
      accepts; otherwise retained as reproducibility artifact).
