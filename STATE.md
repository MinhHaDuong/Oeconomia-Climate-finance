# State

Last updated: 2026-03-25

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
- Incremental caches in `enrich_cache/` survive DVC re-runs (#306, #307, #298)
- LLM extraction cache: sha256(chunk):model key, JSONL in enrich_cache/ (#298)
- Language enrichment: two-pass (OpenAlex API + langdetect), folded into `enrich_works` DVC stage (#423)
- Language utilities (`normalize_lang`, `detect_language`, `ISO_639_1_CODES`) shared via `utils.py`
- DVC clean, 18 files pushed

## Build system

- `make manuscript` is Phase 3 pure: only `quarto render` (no Python, no stats, no API)
- `make figures-manuscript` uses frozen v1 archive data (`config/v1_tab_alluvial.csv`, `config/v1_cluster_labels.json`)
- `make figures` regenerates full-corpus figures for data paper / companion
- `make papers` idempotent: each paper depends on its own vars file; lexical figures use sentinel stamp
- `corpus_sources` derived from `SOURCE_NAMES` length (not hardcoded)
- Syllabi fetch parallelized: 100 workers, per-host rate limiting
- Pipeline progress bars with stuck detection via WatchedProgress (#288)
- LLM calls via litellm with provider-prefixed model strings (#289)

## Blockers

None.

## Active PRs

- #385: docs: landscape analysis of distributed issue trackers (#237)
- #386: ✅ merged — data management plan (CNRS/Science Europe model)
- #387: ✅ merged — eager branching workflow (Dreaming on a branch)
- #425: ✅ merged — language enrichment via OpenAlex + langdetect (#423, #427)

## Recent (2026-03-24 rally loop)

- #289: ✅ litellm migration — all 3 LLM scripts use litellm.completion()
- #288: ✅ WatchedProgress infrastructure — Rich progress bars + stuck detection
- #299: ✅ Clustering comparison — KMeans/HDBSCAN/Spectral across 3 spaces
- #311: ✅ Data paper editorial — 30+ sub-issues, scispace rename, computed vars
- #298: ✅ LLM extraction cache — per-chunk cache survives DVC re-runs
- #342: ✅ Extract cache tests (RED phase, subsumed by #298)
- #382: ✅ Teaching pipeline test drift — 3 test fixes
- #381: ✅ Script hygiene — archived experimental script, fixed sys.path hack
- Test suite: 517 passed, 2 failed (god modules + clustering plots, both pre-existing)

## Next actions

- Finalize DMP on OPIDoR (after v1.1 counts stabilize)
- Send Errata 1 to Oeconomia editor
- Data paper submission (RDJ4HSS) — PDF ready at `output/content/data-paper.pdf`
- ESHET-HES conference slides (Nice, May 26–29)
- #310: Ship all rows (restructure Zenodo deposit)

## Open tickets (publication path)

- #310: Ship all rows — restructure Zenodo deposit

## Open tickets (tooling)

- #255: Metadata completeness (DOI backfill)
- #297: Unix-style figure scripts
- #376: Setup: rename repo, create oeconomia release branch
- #428: Normalize enrichment tables (join stage instead of in-place mutation)
- #432: Make save_csv atomic (write-then-rename)

## Open tickets (backlog)

- #26: Human proofread of full manuscript
- #158: Third paper (agentic workflow)
- #223: Worktrees start without DVC data
- #391: Harness extraction (started; agentic-harness repo created, docs transferred; prior art: PR #224)
- #253: LLM audit on Padme
- #262: Continuous relevance score
