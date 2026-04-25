# State

Last updated: 2026-04-25

## Current goal

**Null ribbon quality** — all 18 zoo figures have ribbons (drivers done); fix scaling, axis, and L3 methodology.

### Roadmap
1. **NOW — Ribbon quality** (tickets 0112–0115): fix Z-score rescaling, L2 mismatch, L3 document shuffle, analytical overlay.
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

### Null model drivers — all wired 2026-04-25 (PRs #757–#760)
- #757 (0096): multilayer-detection techrep
- #758 (0109): G1/G5/G6/G8 citation null drivers
- #759 (0107+0109): C2ST null model drivers + smoke tests
- #760 (0111): dispatcher split — compute_null_model.py → 193L; 6 new driver modules

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS, SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
Being re-generated on padme with GROBID reference extraction and DOI matching.

## Known test failures (pre-existing RED)

- `test_doc_vars_no_extras[technical-report|multilayer-detection]`: unused DOC_VARS entries. Pre-existing.
- `test_robustness_observability.py::test_step1_counter_attempted`: flaky under `-n 4`. Pre-existing.

## Blockers

None.

## Null model ribbon status

| Method | Status |
|--------|--------|
| S1_MMD | ✅ ribbon live |
| S2_energy | ✅ ribbon live |
| S3_sliced_wasserstein | ✅ CSV computed; ribbon live |
| S4_frechet | ✅ CSV computed; ribbon live |
| L1 | ✅ ribbon live |
| L2 | ✅ CSV computed; ribbon live (scale bug → ticket 0112) |
| L3 | ✅ CSV computed; ribbon missing (window filter bug → ticket 0114) |
| G1_pagerank | ✅ CSV computed; ribbon live |
| G2_spectral | ✅ ribbon live |
| G3_coupling_age | ❌ no null model (G3/G4/G7 not in null pipeline) |
| G4_cross_tradition | ❌ no null model |
| G5_pref_attachment | ✅ CSV computed; ribbon live |
| G6_entropy | ✅ CSV computed; ribbon live |
| G7_disruption | ❌ no null model |
| G8_betweenness | ✅ CSV computed; ribbon live |
| G9_community | ✅ ribbon live |
| C2ST_embedding | ✅ CSV computed; ribbon live (scale offset → ticket 0113) |
| C2ST_lexical | ✅ CSV computed; ribbon live (scale offset → ticket 0113) |

## Open ribbon-quality tickets

| Ticket | Title | Priority |
|--------|-------|----------|
| 0112 | Fix L2 null: filter crossyear to resonance-only | High |
| 0113 | Drop Z-score rescaling; plot raw statistic values | High |
| 0114 | L3 null: full document shuffle + window="0" ribbon | High |
| 0115 | Analytical null overlay for S1/S2/L1/C2ST | Medium |

## Next actions

- Land 0113 first (raw values — unblocks all downstream ribbon work)
- Then 0112 (L2 scale fix), 0114 (L3 document shuffle), 0115 (analytical overlay)
- Branch `t0107-null-model-c2st-drivers` needs PR opened and rebase onto main (picks up 0111 split)
- Beat in progress on 0066 (null CSV schema validation)

Background (not on critical path):

- **0071-0078** bias audit — narrative backing for §4.8 Robustness / §6.4 Limitations
- Re-land arch rule 9 (tickets 0043/0044)
