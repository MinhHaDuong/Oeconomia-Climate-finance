# State

Last updated: 2026-03-23

## Status: SUBMITTED + ERRATA 1

Submitted to Oeconomia (Varia) on 2026-03-18. Under double-blind review.
- Zenodo: https://doi.org/10.5281/zenodo.19097045
- HAL: hal-05558422v1
- Git tag: v1.0-submission
- Errata 1 ready in `release/2026-03-23 Oeconomia errata/` (Figure 2 label fix)

## Manuscript

- ~8,860 words, 61 bib entries — submitted as anonymized PDF
- 2 figures (bars_v1, composition) + 2 tables (traditions, venues), no supplement
- Manuscript decoupled from live corpus: frozen archive data in `config/v1_*`, pinned vars in `manuscript-vars.yml`
- Figure 2 labels corrected (Errata 1): 5/6 cluster titles were mapped to wrong panels
- `compute_vars.py` skips manuscript — vars are manually maintained

## Corpus (v1.1)

- 6 sources: OpenAlex, ISTEX, bibCNRS (news/discourse), SciSpace, grey literature, teaching canon
- Semantic Scholar disconnected: keyword search was broken (wrong endpoint, no phrase matching)
- 31,012 refined works, 637,444 citations, 37,928 embeddings
- Teaching expanded: 622 works from 52 institutions (scraper + LLM extraction)
- Filtering pipeline renamed from "refinement" (#261)
- `in_v1` provenance column: 29,805 / 31,012 rows match v1.0-submission (96.1%)
- Incremental caches in `enrich_cache/` survive DVC re-runs (#306, #307)
- DVC clean, 18 files pushed

## Build system

- `make manuscript` is Phase 3 pure: only `quarto render` (no Python, no stats, no API)
- `make figures-manuscript` uses frozen v1 archive data (`config/v1_tab_alluvial.csv`, `config/v1_cluster_labels.json`)
- `make figures` regenerates full-corpus figures for data paper / companion
- `corpus_sources` derived from `SOURCE_NAMES` length (not hardcoded)
- Syllabi fetch parallelized: 100 workers, per-host rate limiting

## Blockers

None.

## Active PRs

- #264: docs: landscape analysis of distributed issue trackers (#237) — stale

## Next actions

- Send Errata 1 to Oeconomia editor
- Data paper submission (RDJ4HSS) — PDF ready at `output/content/data-paper.pdf`
- ESHET-HES conference slides (Nice, May 26–29)
- #299: Clustering comparison (HDBSCAN/Spectral/BERTopic) — overnight programme
- #310: Ship all rows (restructure Zenodo deposit)

## Open tickets (publication path)

- #286: Rebuild data paper PDF ✅ done
- #287: DVC commit + push ✅ done
- #299: Clustering comparison (tracking, 6 sub-issues #300–#305)
- #310: Ship all rows — restructure Zenodo deposit

## Open tickets (tooling)

- #255: Metadata completeness (DOI backfill)
- #288: Pipeline watchdogs + progress bars
- #289: Replace hand-rolled LLM calls with litellm
- #297: Unix-style figure scripts
- #298: Cache LLM extraction results
- #306: Citations cache ✅ merged
- #307: Embeddings cache ✅ merged

## Open tickets (backlog)

- #26: Human proofread of full manuscript
- #158: Third paper (agentic workflow)
- #223: Worktrees start without DVC data
- #236–240: Harness extraction
- #253: LLM audit on Padme
- #261: Rename refinement → filtering ✅ merged
- #262: Continuous relevance score
