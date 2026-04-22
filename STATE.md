# State

Last updated: 2026-04-22

## Current goal

**A solid narrative backed by robust key results and clear figures** for the companion method paper (epic 0026, QSS target).

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
- `companion-paper.qmd`: method paper for QSS, reimagined 2026-04-15 (epic 0026); lean 6-method panel
- NCC epic (0012): closed as won't-do — "Paris didn't matter" oversold the data

### Zoo deepening — merged 2026-04-22 (PRs #744–#752)
- #744 (0099 part 1): L1_js theory — smoothing, vocabulary, low-n warning (LOW_N_LEXICAL_THRESHOLD=50)
- #745 (0097): null model CI bands in zoo result figures
- #746 (0099 part 2): L2 null expectation + C2ST_lexical D/n guard
- #747 (0098 partial): growing-corpus bias theory + --no-equal-n flag
- #748 (0101): minimum corpus size theory + per-method config overrides
- #749 (0103): figure polish — config-driven method titles, Z=0 reference line
- #750 (0100): gap=1 window semantics across all four channels
- #751/#752: hotfixes — L2 w=5 test exemption, crossyear Z-score all-NaN crash

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS (news/discourse), SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
- Being re-generated on padme with: explode Unstructured reference in citation targets (with GROBID), search citation targets DOI, matching parsed refs to corpus works, cleanup string encodings.

## Blockers

None.

## Active agents (as of 2026-04-22)

Four Claude processes running on padme, each in its own locked worktree:
- `t0083-sensitivity-annex` (`agent-aa72c17c`): sensitivity annex — 8 commits in, compute_sensitivity_grid.py + plot_companion_sensitivity.py ready, needs GPU run
- `t0098-bias-comparison-figures` (`agent-a05d098e`): bias comparison figures — plot_zoo_bias_comparison.py done, needs PR
- `t0099-l2-c2st` (`agent-a6cd5236`): L2/C2ST_lexical zoo prose — 3 commits in, likely ready for PR
- `orchestrate-98-83-84` (`agent-a952b232`): orchestrator planning branch for 0098/0083/0084

## Next actions

In direct service of the current goal (narrative + results + figures):

- **0083** sensitivity annex — evidence that the key results (G9 sub-zones, S2/L1 saturation) are robust across window, gap, embedding dim, embedding model. R=3 median per cell, ~1.5-2h GPU on padme. Agent in progress.
- **0084** subsampling-variance ribbon — honest uncertainty on the headline Z-plot. R=20 trim-2, ~2h GPU.
- **0098** bias comparison figures — agent in progress on `t0098-bias-comparison-figures`.
- **0070 + 0071-0078** bias audit — narrative backing for §4.8 Robustness and §6.4 Limitations. Most are acknowledgements; some warrant child analyses.
- Waiting for corpus **1.1.2** to finish building — enables a rerun if the enriched corpus meaningfully changes G9's sub-zone structure.

Background work (not on the critical path for the current goal):

- **0025** connective prose for corpus report
- **0092** wire zoo figure recipes in dedicated `zoo.mk` (17 schematics + 18 result panels) — prerequisite for `make output/content/breakpoint-detect-method-zoo.pdf` end-to-end
- Re-land arch rule 9 (corpus access through loaders only) — tickets 0043/0044 already on main
- **0081** bootstrap CI (pytest on PR/push) — prerequisite for 0079 and for /verify to have mechanical evidence; cross-repo batch with IDH 0015, git-erg 0003, AEDIST 0111. Stabilise flakes first; then branch protection.
