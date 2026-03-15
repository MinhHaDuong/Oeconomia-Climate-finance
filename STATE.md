# State

Last updated: 2026-03-15

## Manuscript

- ~9,600 words (target ~9,000), 61 bib entries
- 3 figures (emergence, breakpoints, alluvial) + 2 tables (traditions, poles)
- Variable dependencies reduced to 1 (`corpus_total_approx`)
- Phase 2→3 contract documented in manuscript.qmd header comment
- ΔBIC values, cluster counts, language % moved out of prose (belong in companion)

## Corpus

- 27,534 refined works (from 35,143 unified), embeddings + citations cached
- Schema normalized: `from_openalex`, `from_s2`, ..., `from_teaching` boolean columns (1NF)
- DVC-managed: `dvc.yaml` (5 stages), `dvc.lock` committed, remote padme in sync
- DVC cache external: `/home/haduong/data/projets/.../dvc-cache` (hors Nextcloud)
- Validation: `make corpus-validate` 42 passed, 1 pre-existing failure (duplicate DOIs)
- `make check-fast`: 194 passed, 0 failures
- Ecology filter tightened — need extend + filter + figures regen

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992
- Fig 2 (composition): relocated to §3.4 (thematic decomposition argument)
- Fig S1 (traditions): co-citation network, color, Electronic Supplement (PR #88 merged)
- Table 2 (poles): efficiency vs accountability terms — done
- Table 1 (traditions): caption updated; §1.5 cites co-citation evidence (Q=0.68)

## Blockers

- Table 1 pending: co-citation communities don't cleanly separate pre-2007 traditions
- Corpus regen needed after ecology filter tightening

## Active PRs

- #99: docs — reasoning levels for git messages
- #127: extract housekeeping/memory sections from AGENTS.md into runbooks
- #128: DOI dedup in corpus_refine

## Recent

- **DVC chantier complete** (2026-03-15): 10 tickets, data versioned with DVC, pipeline DAG, repro archives, external cache, bidirectional push/pull doudou ↔ padme.
- **Source normalized to 1NF** (#113): pipe-separated `source` → boolean `from_*` columns. 15 scripts adapted.
- **Teaching canon refactored** (#114): single merge in discover, `build_teaching_canon.py` simplified (363 → 100 lines), `teaching_canon.csv` eliminated.
- **Test infra complete** (#117–#123, #129–#130): `pytest-timeout`, `make check-fast` (194 passed, 0 failures). Makefile contract tests updated for DVC delegation; corpus_refine tests skip torch offline.
- **Flags column normalized** (#126): removed derived `flags` list from `extended_works.csv`; booleans are source of truth, pipe-string serialized to `corpus_audit.csv` only at write time. Three reconstruction guards deleted.
- **CLIMATE_FINANCE_DATA removed**: scripts hardcode `data/` relative to repo root. `.env` simplified.

## Open tickets

- #125: DVC-track exports/ and syllabi/

## Next priorities

1. Human proofread of full manuscript
2. Merge PR #128 (DOI dedup) + PR #99 (docs)
3. Corpus regen (extend + filter + figures after ecology filter tightening)
4. Regen period detection curves + terms table for §2.5
5. Move ΔBIC details + cluster counts to companion paper
