# State

Last updated: 2026-04-26

## Current goal

**Analytical null overlays** — C2ST done; L1 (0124) and S1/S2 (0125) remain. Then replication ribbon.

### Roadmap
1. **NOW — Analytical null** (tickets 0124, 0125): L1 JS formula, S1 MMD²/S2 energy formulas.
2. **NEXT — Replication ribbon** (ticket 0105): R=20 equal-n subsamples → [Q10,Q90] band on S1–S4 and C2ST×2.
3. **AFTER — Paper method section**: narrative, figures, and prose for `multilayer-detection.qmd`.

## Status: TWO PAPERS SUBMITTED + ALL NULL DRIVERS WIRED

### Oeconomia (Varia) — submitted 2026-03-18
Under double-blind review. ~8,860 words, 61 bib entries, 2 figures, 2 tables.
- Zenodo: https://doi.org/10.5281/zenodo.19097045
- HAL: hal-05558422v1
- Git tag: v1.0-submission
- Branch: `submission/oeconomia-varia`
- Decoupled from live corpus: frozen archive data in `config/v1_*`, pinned vars in `manuscript-vars.yml`
- Errata 1 ready in `release/2026-03-23 Oeconomia errata/` (Figure 2 label fix)

### RDJ4HSS (data paper) — submitted 2026-03-26
Under review (peer reviewers + data specialists). 2,495 words, 1 figure, 3 tables, 10 bib entries.
- Zenodo: https://doi.org/10.5281/zenodo.19236130
- Git tag: v1.1-rdj-submitted
- Branch: `submission/rdj-data-paper`

### Technical reports — modularized 2026-04-21 (PRs #718 / #725 / #727)
- `corpus-report.qmd`, `technical-report.qmd`, `multilayer-detection.qmd` (QSS target)
- Zoo includes: `_includes/zoo/` one file per method, cherry-pickable

### Zoo deepening — merged 2026-04-22 (PRs #744–#754)
- Null model CI bands, figure polish, bias comparison, sensitivity annex, window semantics

### Null model drivers — all wired 2026-04-25 (PRs #757–#762)
- #757 (0096): multilayer-detection techrep
- #758 (0109): G1/G5/G6/G8 citation null drivers
- #759 (0107+0109): C2ST null model drivers + smoke tests
- #760 (0111): dispatcher split — compute_null_model.py → 193L; 6 new driver modules
- #761 (0066): null CSV schema validation on read in export_divergence_summary
- #762: fix zoo.mk null deps (NULL_METHODS_ALL loop); ribbon quality tickets 0112–0116

### Ribbon raw values + smoke test fixes — merged 2026-04-25 (PRs #763–#767)
- #763: prune dead DOC_VARS entries (test_doc_vars_no_extras green)
- #764 (0118): S4_frechet empty-results guard + smoke-mode min_papers precedence
- #765 (0112): fix L2 null: filter crossyear to resonance-only
- #766 (0113): zoo figures: plot raw D(t,w) values, drop Z-score rescaling
- #767 (0119): regenerate golden values (102-work smoke fixture, 96 rows)

### Null ribbon quality + analytical null — merged 2026-04-26 (PRs #768–#769)
- #768 (0114): L3 null model: document-shuffle permutations + window="0" ribbon
- #769 (0115): C2ST analytical null overlay (Hanley-McNeil); `--analytical-null` plot flag; zoo.mk targets

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS, SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
Being re-generated on padme with GROBID reference extraction and DOI matching.

## Known test failures (pre-existing RED)

- `test_robustness_observability.py::test_step1_counter_attempted`: flaky under `-n 4`. Pre-existing.
- `test_ref_match_corpus.py::TestRefMatchCorpus::*`: flaky under `-n 4` parallel execution; all pass in isolation. Pre-existing.

## Blockers

None.

## Null model ribbon status

| Method | Status |
|--------|--------|
| S1_MMD | ✅ ribbon live (raw values) |
| S2_energy | ✅ ribbon live (raw values) |
| S3_sliced_wasserstein | ✅ ribbon live (raw values) |
| S4_frechet | ✅ ribbon live (raw values) |
| L1 | ✅ ribbon live (raw values) |
| L2 | ✅ ribbon live — scale bug → ticket 0112 |
| L3 | ✅ ribbon live (document-shuffle permutations + raw burst counts, PR #768) |
| G1_pagerank | ✅ ribbon live (raw values) |
| G2_spectral | ✅ ribbon live |
| G3_coupling_age | ❌ no null model (G3/G4/G7 not in null pipeline) |
| G4_cross_tradition | ❌ no null model |
| G5_pref_attachment | ✅ ribbon live (raw values) |
| G6_entropy | ✅ ribbon live (raw values) |
| G7_disruption | ❌ no null model |
| G8_betweenness | ✅ ribbon live (raw values) |
| G9_community | ✅ ribbon live |
| C2ST_embedding | ✅ ribbon live (raw values) + analytical overlay (0115) |
| C2ST_lexical | ✅ ribbon live (raw values) + analytical overlay (0115) |

## Open ribbon-quality tickets

| Ticket | Title | Priority |
|--------|-------|----------|
| 0124 | L1 analytical null overlay (JS divergence, Archer 2014) | Medium |
| 0125 | S1/S2 analytical null overlay (Gretton 2012, Székely-Rizzo 2013) | Medium |

## Open infrastructure tickets

| Ticket | Title | Priority |
|--------|-------|----------|
| 0116 | Add n_jobs parallelism to L2/L3 null model permutation drivers | Low |
| 0120 | Empty-results guard for remaining dispatcher modules (_c2st, _community, _citation, _lexical) | Low |
| 0121 | Standing regression test: all dispatcher methods return valid schema on empty corpus | Low |

## Next actions

- 0124 (L1 analytical null, Archer formula)
- 0125 (S1/S2 analytical nulls, kernel/U-stat formulas)
- 0105 (replication ribbon: R=20 equal-n subsamples)

Background (not on critical path):

- **0071-0078** bias audit — narrative backing for §4.8 Robustness / §6.4 Limitations
- Re-land arch rule 9 (tickets 0043/0044)
