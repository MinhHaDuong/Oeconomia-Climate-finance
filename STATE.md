# State

Last updated: 2026-04-24

## Current goal

**Null model ribbons on all 18 zoo figures** — every animal shows a time-varying permutation null CI band (w=3) instead of the flat ±2 box.

### Roadmap
1. **NOW — Null model ribbons** (this goal): implement missing permutation drivers; run all null CSVs on padme.
2. **NEXT — Replication ribbon** (ticket 0105): R=20 equal-n subsamples → [Q10,Q90] band on S1–S4 and C2ST×2.
3. **AFTER — Paper method section**: narrative, figures, and prose for `multilayer-detection.qmd`.

## Status: TWO PAPERS SUBMITTED + WAVE C MERGED (COMPANION PAPER ASSEMBLED)

### Oeconomia (Varia) — submitted 2026-03-18
Under double-blind review. ~8,860 words, 61 bib entries, 2 figures, 2 tables.
- Zenodo: https://doi.org/10.5281/zenodo.19097045
- HAL: hal-05558422v1
- Git tag: v1.0-submission
- Branch: `submission/oeconomia-varia`
- Decoupled from live corpus: frozen archive data in `config/v1_*`, pinned vars in `manuscript-vars.yml`
- Errata 1 ready in `release/2026-03-23 Oeconomia errata/` (Figure 2 label fix)
- Errata addressee corrected: Lenfant (Editor-in-Chief), not Sergi

### RDJ4HSS (data paper) — submitted 2026-03-26
Under review (peer reviewers + data specialists). 2,495 words, 1 figure, 3 tables, 10 bib entries.
- Zenodo: https://doi.org/10.5281/zenodo.19236130
- Git tag: v1.1-rdj-submitted
- Branch: `submission/rdj-data-paper`

### Technical reports — modularized 2026-04-21 (PRs #718 / #725 / #727)
- `corpus-report.qmd`: corpus construction, data quality, corpus contents, software environment
- `technical-report.qmd`: pure composer. Four includes: `_includes/techrep/overview.md`, `_includes/techrep/zscore.md`, `_includes/techrep/summary-of-findings.md`, `_includes/techrep-zoo.md`
- `_includes/techrep-zoo.md`: composer for the 18-method zoo. One file per method under `_includes/zoo/` (S1–S4, S5=C2ST_embedding, L1–L3, L4=C2ST_lexical, G1–G9). Cherry-pickable by other documents.
- `breakpoint-detect-method-zoo.qmd`: thin wrapper that renders just the zoo (companion to the TR, or standalone reference)
- `multilayer-detection.qmd`: method paper for QSS (renamed from companion-paper, #737); lean 6-method panel
- NCC epic (0012): closed as won't-do — "Paris didn't matter" oversold the data

### Zoo deepening — merged 2026-04-22 (PRs #744–#754)
- #744 (0099 part 1): L1_js theory — smoothing, vocabulary, low-n warning (LOW_N_LEXICAL_THRESHOLD=50)
- #745 (0097): null model CI bands in zoo result figures
- #746 (0099 part 2): L2 null expectation + C2ST_lexical D/n guard
- #747 (0098 partial): growing-corpus bias theory + --no-equal-n flag
- #748 (0101): minimum corpus size theory + per-method config overrides
- #749 (0103): figure polish — config-driven method titles, Z=0 reference line
- #750 (0100): gap=1 window semantics across all four channels
- #751/#752: hotfixes — L2 w=5 test exemption, crossyear Z-score all-NaN crash
- #753 (0098 figures): bias comparison figures — plot_zoo_bias_comparison.py + Make recipes
- #754 (0083): companion paper sensitivity annex — compute_sensitivity_grid.py + plot_companion_sensitivity.py

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS (news/discourse), SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
- Being re-generated on padme with: explode Unstructured reference in citation targets (with GROBID), search citation targets DOI, matching parsed refs to corpus works, cleanup string encodings.

## Known test failures (pre-existing RED)

- `test_doc_vars_no_extras[technical-report]` and `test_doc_vars_no_extras[multilayer-detection]`: dead entries in `DOC_VARS` (vars declared but not referenced in prose). Pre-existing; not blocking.
- `test_robustness_observability.py::test_step1_counter_attempted`: flaky under `-n 4` parallel execution; passes alone. Needs stabilisation.

## Blockers

None.

## Null model ribbon status

| Method | Status |
|--------|--------|
| S2_energy | ✅ ribbon live |
| L1 | ✅ ribbon live |
| G2_spectral | ✅ ribbon live |
| G9_community | ✅ ribbon live |
| S1_MMD | ✅ done 2026-04-24 |
| S3_sliced_wasserstein | 🔄 computing (padme GPU) |
| S4_frechet | 🔄 computing (padme GPU) |
| C2ST_embedding | ❌ needs driver (ticket 0107) |
| C2ST_lexical | ❌ needs driver (ticket 0107) |
| L2 | ❌ needs driver (ticket 0108) |
| L3 | ❌ needs driver (ticket 0108) |
| G1_pagerank | ❌ needs driver (ticket 0109) |
| G3_coupling_age | ❌ needs driver (ticket 0109) |
| G4_cross_tradition | ❌ needs driver (ticket 0109) |
| G5_pref_attachment | ❌ needs driver (ticket 0109) |
| G6_entropy | ❌ needs driver (ticket 0109) |
| G7_disruption | ❌ needs driver (ticket 0109) |
| G8_betweenness | ❌ needs driver (ticket 0109) |

When S3/S4 finish: `make zoo-figures` picks up the new CSVs automatically via `$(wildcard)`.

## Next actions

- **0107** — C2ST null model drivers (companion paper panel: highest priority)
- **0108** — L2/L3 null model drivers
- **0109** — G1/G3–G8 null model drivers (7 graph methods, largest effort)
- After S3/S4 complete: commit the two new null CSVs and rebuild zoo figures

Background (not on critical path):

- **0071-0078** bias audit — narrative backing for §4.8 Robustness / §6.4 Limitations
- Re-land arch rule 9 (tickets 0043/0044)
