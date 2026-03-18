# Roadmap

## North star

Climate finance crystallized as an economic object by ~2009. Everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought within the categories established at that moment. This paper traces how economists and institutions co-produced those categories.

## Current milestone: Revision

- [x] Fix teaching source pipeline (#135)
- [ ] Corpus regen on padme (in progress) → figures, tables, variables update
- [ ] Human proofread of full manuscript (#26)
- [ ] Final word count trim (~9,600 → ~9,000)
- [ ] Final `make clean && make all` + visual check
- [ ] Move draft to `release/` for submission

## Next milestone: Submission packaging

- [x] Analysis archive ships output checksums (#210)
- [ ] Tag repo `v1.0-submission` + push tag
- [ ] Archive on Zenodo (via GitHub integration) → get DOI
- [ ] Upload technical report to HAL as working paper → get HAL ID
- [ ] Add "Data and code availability" paragraph to manuscript
- [ ] Draft cover letter pointing reviewers to HAL + Zenodo
- [ ] Companion methods paper (Scientometrics/QSS): parked for post-acceptance

## Post-submission improvements

- [x] Split embeddings encoding (Phase 1) from UMAP+clustering (Phase 2) (#189)
- [ ] Split remaining enrich stages into independent DVC stages
- [ ] Re-enable Semantic Scholar with API key
- [ ] JETP query: add concept filter to exclude physics journal noise

## Completed

- Foundations: figures, bibliography audit, empirical findings
- Drafting: all sections (intro, §1–§4, conclusion)
- Œconomia house style, AI-tell sweep, code audit, PDF+ODT build clean
- Doc restructuring: separated concerns (AGENTS → workflow only, domain guidance → docs/), added Dragon Dreaming + TDD + git hooks
- Agent-agnostic skills: runbooks/, make check, AGENTS.md works with any AI assistant
- Agent identity (#109): machine user `HDMX-coding-agent`, classic PAT in `.env`, convention documented in AGENTS.md
- DVC integration (#101–#104, #109): data versioning, pipeline DAG, repro archives, external cache, bidirectional sync
- Source normalized to 1NF (#113): pipe-separated source → boolean from_* columns
- Teaching canon refactored (#114): single merge, build_teaching_canon simplified 363→100 lines
- Test infra (#117–#123, #129–#130): pytest-timeout, make check-fast
- Flags column normalized (#126): removed derived list from extended_works.csv; boolean columns are source of truth
- catalog_bibcnrs as DVC stage (#134): data/exports/ DVC-tracked
- Teaching source pipeline (#135): scraped syllabi → YAML → teaching_works.csv
- Split discover into per-source DVC stages (#152): parallel, granular, skippable
- OpenAlex --from-date incremental filtering (#153): budget-aware, sidecar auto-detect
- Venue table replaces fig-seed (#150, #151): @tbl-venues in §3.4 body
- Companion paper complete draft (#149): all sections filled
- Retry robustness + budget guard (#171): unified retry_get, API key fix, budget-aware fetch
- Split embeddings (#189): enrich_embeddings.py (Phase 1 encoding) + analyze_embeddings.py (Phase 2 UMAP+clustering)
- Phase separation + manuscript cleanup (#189b): surgical Makefile deps, no API calls in Phase 3, structural break purge, layout fixes
