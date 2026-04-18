# State

Last updated: 2026-04-18

## Status: TWO PAPERS SUBMITTED + WAVE C MERGED (COMPANION PAPER ASSEMBLED, PRE-SUBMISSION POLISH NEXT)

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

### Technical reports — restructured 2026-04-14 (PR #649)
- `corpus-report.qmd`: corpus construction, data quality, corpus contents, software environment
- `technical-report.qmd`: analysis methods and results (structural breaks, thematic structure, polarization, citations); 15-method divergence zoo lives here as includes (ticket 0028)
- `companion-paper.qmd`: method paper for QSS, reimagined 2026-04-15 (epic 0026); lean 6-method panel
- NCC epic (0012): closed as won't-do — "Paris didn't matter" oversold the data

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS (news/discourse), SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
- Being re-generated on padme with: explode Unstructured reference in citation targets (with GROBID), search citation targets DOI, matching parsed refs to corpus works, cleanup string encodings.

## Blockers

None for the current goal. Wave C merged 2026-04-18 (PRs #708 / #709 / #710). Companion paper is now assembled on main with method, figures, and §5 numeric fill from the 2026-04-17 corpus-1.1.1 pipeline rerun. Pre-submission polish (0083 sensitivity annex, 0084 subsampling ribbon) is next but not blocking.

### Wave C — merged 2026-04-18
- #708 (ticket 0057): §4 Method rewrite + §5 stubs + bibliography for two-sample testing literature
- #709 (ticket 0058): four canonical figures (Z-series, heatmap, terms, community) + shared plot utilities + `companion.mk`
- #710 (ticket 0064): §5 Results filled from real-corpus vars — four G9 sub-zones at lead $w=3$ (2001-2002, 2006, 2012-2015, 2018-2020, peak Z=8.16 at 2015); S2/L1 saturate under residual growth bias (B2/B9), reframed as diagnostic

### Divergence pipeline — merged 2026-04-15 (PR #650)
- 15 divergence methods (S1-S4 semantic, L1-L3 lexical, G1-G8 citation graph)
- 3 change point detectors (PELT, DynP, KernelCPD), convergence analysis
- Embedding sensitivity analysis (PCA sweep, JL random projections)
- Architecture: dispatcher pattern, modular Makefile (`divergence.mk`), Pandera schema, config-driven
- `pipeline_loaders.py`: new `load_refined_works()` layer; all divergence modules use `load_analysis_corpus()`

## Next actions

- **Companion paper polish** before submission-branch sprout:
  - **0083** sensitivity annex (window × gap × embedding dim × model, R=3 median) — ~1.5-2h GPU on padme
  - **0084** subsampling-variance ribbon on the headline Z-plot (R=20 trim-2) — ~2h GPU
  - Three small follow-up items remain on #708's merge (abstract "three sub-zones" vs `g9_n_zones: 4`; §5.1 hard-coded cross-w numbers; prose register "smoking gun" → "diagnostic signature") — land as a consolidated pre-sprout polish PR
- **0070 bias audit** + child tickets 0071-0078: pre-submission defence-in-depth for §4.8 and §6.4 (most are narrative acknowledgements, some warrant child analyses)
- **0025**: connective prose for corpus report
- **0028**: modular analysis report (one include per script) — home for the 15-method divergence zoo
- Re-land arch rule 9 (corpus access through loaders only) on own branch — tickets 0043/0044 already on main
- Waiting for corpus 1.1.2 to finish building (enables a possible rerun before submission)
- **0081 bootstrap CI** (pytest on PR/push) — prerequisite for 0079 (cached baseline failure set) and for /verify to have mechanical evidence; part of the cross-repo CI batch with IDH 0015, git-erg 0003, AEDIST 0111. Stabilise flakes first; then branch protection requiring `tests`.
