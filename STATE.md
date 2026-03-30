# State

Last updated: 2026-03-30

## Status: TWO PAPERS SUBMITTED

### Oeconomia (Varia) — submitted 2026-03-18
Under double-blind review.
- Zenodo: https://doi.org/10.5281/zenodo.19097045
- HAL: hal-05558422v1
- Git tag: v1.0-submission
- Branch: `submission/oeconomia-varia`
- Errata 1 ready in `release/2026-03-23 Oeconomia errata/` (Figure 2 label fix)

### RDJ4HSS (data paper) — submitted 2026-03-26
Under review (peer reviewers + data specialists).
- Zenodo: https://doi.org/10.5281/zenodo.19236130
- Git tag: v1.1-rdj-submitted
- Branch: `submission/rdj-data-paper`
- 2,495 words, 1 figure, 3 tables, 10 bib entries

## Manuscript (Oeconomia)

- ~8,860 words, 61 bib entries — submitted as anonymized PDF
- 2 figures (bars_v1, composition) + 2 tables (traditions, venues), no supplement
- Manuscript decoupled from live corpus: frozen archive data in `config/v1_*`, pinned vars in `manuscript-vars.yml`
- Figure 2 labels corrected (Errata 1): 5/6 cluster titles were mapped to wrong panels

## Corpus (v1.1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS (news/discourse), SciSpace, grey literature, teaching canon
- 42,922 raw → 31,713 refined works, 38,479 embeddings, 968,871 citations
- Teaching expanded: 622 works from 52 institutions (scraper + LLM extraction)
- Citation pipeline: cache-is-data architecture (#441), hardened with atomic writes + crash tolerance + no-DOI dedup (#529)
- Fuzzy ref matching: GROBID-parsed refs matched to corpus works via rapidfuzz token_sort_ratio ≥ 85 with year ±1 blocking (#539)
- DVC clean, 18 files pushed
- Enrichment pipeline split into independent DVC stages (#428, #505)
- Code smells cleared: all ruff C901/PLR0912/PLR0915 smell thresholds pass (#507)
- PDF output now opt-in (`--pdf`): `save_figure()` default flipped (#544), phantom flag removed from non-plotting scripts (#545)
- God module split: `analyze_genealogy.py` (808L) → 3 scripts M/V architecture (#542), robustness block to `analyze_cocitation.py`
- Infrastructure sprint (#508–#514): smoke pipeline, I/O discipline, Makefile namespaces, parameterized K, revision runbook, performance baseline
- Feather handoff (#527, #528): Phase 2 reads Feather instead of CSV (~48s → ~1.5s cumulative parse time), `analyze_embeddings` removed from DVC pipeline, pyarrow added

## Blockers

None.

## Next actions

- Send Errata 1 to Oeconomia editor
- Finalize DMP on OPIDoR
- ESHET-HES conference slides (Nice, May 26–29)
- Remaining infrastructure: #515 (DAG viz), #428 (enrichment normalization)
- 1-fig-1-script sweep: #546 (alluvial), #550 (bimodality), #551 (embeddings), #552 (cocitation), #559 (filter_flags LLM extraction)
- #535: Parse unstructured Crossref refs (80K rows with empty metadata)
