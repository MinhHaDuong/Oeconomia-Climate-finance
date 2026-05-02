# State

Last updated: 2026-05-02 21:00 UTC

## Current goal

**Paper method section** — replication ribbon complete (PR #781); null ribbons live for 15/18 methods. Now: write narrative, figures, and prose for `multilayer-detection.qmd`.

### Roadmap
1. ~~**DONE — Ribbon quality** (tickets 0112, 0114, 0115): L2 crossyear fixed, L3 document shuffle done, C2ST analytical null overlay done.~~ PRs merged.
2. ~~**DONE — S4 schema fix** (ticket 0124): restore `year` column in S4_frechet smoke mode.~~ PR #773 merged.
3. ~~**DONE — Replication ribbon** (ticket 0105): R=20 equal-n subsamples → [Q10,Q90] band on S1–S4 and C2ST×2.~~ PR #781 merged.
4. **NOW — Paper method section**: narrative, figures, and prose for `multilayer-detection.qmd`.

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

### Venue concentration (B4 bias) — merged 2026-05-02 (PR #788, ticket 0073)
- `compute_venue_concentration.py`, `plot_venue_concentration.py`, `venues.mk` added
- §4.8 paragraph descoped to ticket 0129

### Ribbon completion + infra fixes — merged 2026-04-29–2026-05-02 (PRs #773–#783)
- #773 (0124): fix S4_frechet smoke-mode min_papers precedence + empty-results guards
- #778 (0120): empty-results guard for _c2st, _community, _citation, _lexical modules
- #779 (0116): add n_jobs parallelism to L2 null model driver
- #780 (0127): fix NameError — import empty_divergence_df in _divergence_semantic
- #781 (0105): replication ribbon for zoo figures (R=20 equal-n subsamples)
- #783 (0122): close ticket — fix parallel test flakiness under pytest-xdist -n 4

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS, SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
Being re-generated on padme with GROBID reference extraction and DOI matching.

## Known test failures (pre-existing RED)

None — parallel flakiness fixed in PR #772 (ticket 0122).

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
| L2 | ✅ ribbon live (raw values, crossyear resonance-only fixed — PR #765) |
| L3 | ✅ ribbon live (document-shuffle permutations — PR merged 0114) |
| G1_pagerank | ✅ ribbon live (raw values) |
| G2_spectral | ✅ ribbon live |
| G3_coupling_age | ❌ no null model (G3/G4/G7 not in null pipeline) |
| G4_cross_tradition | ❌ no null model |
| G5_pref_attachment | ✅ ribbon live (raw values) |
| G6_entropy | ✅ ribbon live (raw values) |
| G7_disruption | ❌ no null model |
| G8_betweenness | ✅ ribbon live (raw values) |
| G9_community | ✅ ribbon live |
| C2ST_embedding | ✅ ribbon live (raw values) |
| C2ST_lexical | ✅ ribbon live (raw values) |

## Open infrastructure tickets

| Ticket | Title | Priority |
|--------|-------|----------|
| 0121 | Standing regression test: all dispatcher methods return valid schema on empty corpus | Low (needs-human) |
| 0126 | Refactor uv invocations to use --env-file (CLAUDE_ENV_FILE leak fix) | Low |
| 0129 | Write §4.8 paragraph on venue concentration bias | Low |

## Next actions

- **0026** / **multilayer-detection.qmd** — paper method section: narrative, figures, prose

Background (not on critical path):

- **0071-0078** bias audit — narrative backing for §4.8 Robustness / §6.4 Limitations (0073 done → PR #788)
- Re-land arch rule 9 (tickets 0043/0044)
