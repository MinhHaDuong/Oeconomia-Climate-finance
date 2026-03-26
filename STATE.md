# State

Last updated: 2026-03-26

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
- 31,204 refined works, 37,928 embeddings
- Teaching expanded: 622 works from 52 institutions (scraper + LLM extraction)
- Filtering pipeline renamed from "refinement" (#261)
- `in_v1` provenance column: 29,805 / 31,012 rows match v1.0-submission (96.1%)
- Citation pipeline: cache-is-data architecture (#441) — each source writes to `enrich_cache/` (crossref_refs.csv, openalex_refs.csv), `merge_citations.py` produces `citations.csv` as a view, Crossref + OpenAlex run in parallel
- Incremental caches in `enrich_cache/` survive DVC re-runs (#306, #307, #298, #441)
- LLM extraction cache: sha256(chunk):model key, JSONL in enrich_cache/ (#298)
- Language enrichment: two-pass (OpenAlex API + langdetect), folded into `enrich_works` DVC stage (#423)
- Language utilities (`normalize_lang`, `detect_language`, `ISO_639_1_CODES`) shared via `utils.py`
- litellm pinned <=1.82.6 (supply chain attack on 1.82.7–1.82.8, PR #447)
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

## Next actions

- Data paper submission (RDJ4HSS) — PDF ready, re-rendered after SciSpace fix (#452)
- Send Errata 1 to Oeconomia editor
- Finalize DMP on OPIDoR (after v1.1 counts stabilize)
- ESHET-HES conference slides (Nice, May 26–29)
