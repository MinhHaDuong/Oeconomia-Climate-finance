# State

Last updated: 2026-04-15

## Status: TWO PAPERS SUBMITTED + DIVERGENCE PIPELINE MERGED

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
- `technical-report.qmd`: analysis methods and results (structural breaks, thematic structure, polarization, citations)
- `companion-paper.qmd`: retired — useful content merging into analysis report (ticket 0024)
- NCC epic (0012): closed as won't-do — "Paris didn't matter" oversold the data

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS (news/discourse), SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations

## Corpus (upcoming 1.1.2)
- Being re-generated on padme with: explode Unstructured reference in citation targets (with GROBID), search citation targets DOI, matching parsed refs to corpus works, cleanup string encodings.

## Blockers

None.

### Divergence pipeline — merged 2026-04-15 (PR #650)
- 15 divergence methods (S1-S4 semantic, L1-L3 lexical, G1-G8 citation graph)
- 3 change point detectors (PELT, DynP, KernelCPD), convergence analysis
- Embedding sensitivity analysis (PCA sweep, JL random projections)
- Architecture: dispatcher pattern, modular Makefile (`divergence.mk`), Pandera schema, config-driven
- `pipeline_loaders.py`: new `load_refined_works()` layer; all divergence modules use `load_analysis_corpus()`

## Next actions

- **0024**: merge companion paper content into analysis report
- **0025**: connective prose for corpus report
- **0028**: modular analysis report (one include per script)
- Re-land arch rule 9 (corpus access through loaders only) on own branch — tickets 0043/0044 already on main
- Run divergence pipeline on real corpus (padme, ticket 0042)
- ESHET-HES conference slides (Nice, May 26–29)
- Charles Gide conference paper (Vannes, July 2–4; paper due June 15)
- Waiting for corpus 1.1.2 to finish building
