# Roadmap

## North star

Climate finance crystallized as an economic object by ~2009. Everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought within the categories established at that moment. This paper traces how economists and institutions co-produced those categories.

## Current milestone: Revision

- [ ] Human proofread of full manuscript
- [ ] Final word count trim (~9,600 → ~9,000)
- [ ] Final `make clean && make all` + visual check
- [ ] Move draft to `release/` for submission

## Next milestone: Submission packaging

- [ ] Tag repo `v1.0-submission` + push tag
- [ ] Archive on Zenodo (via GitHub integration) → get DOI
- [ ] Upload technical report to HAL as working paper → get HAL ID
- [ ] Add "Data and code availability" paragraph to manuscript
- [ ] Draft cover letter pointing reviewers to HAL + Zenodo
- [ ] Companion methods paper (Scientometrics/QSS): parked for post-acceptance

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
- Test infra (#117–#123, #129–#130): pytest-timeout, make check-fast (194 passed, 0 failures)
- Flags column normalized (#126): removed derived list from extended_works.csv; boolean columns are source of truth
- Fix timeout truncation (#121): remove int() cast on request_timeout
- DOI dedup in corpus_refine (#120): fixes duplicate OpenAlex IDs and fake grey-lit placeholder DOIs
