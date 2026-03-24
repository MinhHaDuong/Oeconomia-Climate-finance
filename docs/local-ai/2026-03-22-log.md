# Overnight log — 2026-03-22

Session: started 21:00 (interactive with author), autonomous from ~23:10

## What got done today

### Interactive session (21:00–23:10)
- **#265 merged**: Parallelize syllabi fetch stage (100 workers, per-host 1 req/s). Full TDD cycle + 4-agent self-review. Red team caught PDF collision bug — fixed before merge.
- **Makefile fixes**: wired `corpus-tables` into `figures` target, added `fig_dag` recipe to `DATAPAPER_FIGS`
- **PR #251 merged**: Data paper RDJ4HSS reformat (12 commits, 3 conflict resolutions)
- **Stale test diagnosis**: `test_corpus_table_export` failures were stale CSV — regenerated, root cause was missing Makefile wiring
- **Tickets opened**: #270 (S2 in SOURCE_META), #271 (S2 in data paper), #272 (corpus rebuild)

### Autonomous session (23:10–00:00)
- **S2 harvest completed**: 34,055 works (up from 19,543 in pool — `--resume` found ~14K new papers)
- **catalog_merge completed**: 71,607 unified works (was 41,717 — +72% from S2)
- **PR #274** (#270): S2 added to `export_corpus_table.py` SOURCE_META + sync test
- **PR #276** (#271): S2 added to data-paper.qmd (abstract, Table 1, provenance flags, prose)
- **enrich_works running**: `enrich_dois.py` is doing CrossRef DOI lookups for ~30K new S2 works. 2,269/~30K done after 37min. Rate-limited to ~1 req/s — will take ~8 hours total. Caches incrementally.

## Balance

| Category | Tickets | Approx % |
|----------|---------|----------|
| Deliverable (data paper) | #271 (PR #276) | 25% |
| Tooling (pipeline, SOURCE_META) | #265, #270, #272 | 55% |
| Meta (diagnosis, log, memory) | stale test investigation | 20% |

Tooling exceeded 40% because the corpus rebuild (#272) is the critical blocker for both #270 and #271 to be fully verified.

## Decisions made

- S2 harvest: ran DVC `--resume` which re-queried API (found 14K new papers vs extract-only)
- Cleared 4 stale DVC lock files from dead processes
- Let `enrich_dois.py` run overnight — caches incrementally, next run picks up where it left off
- PR #251 conflict resolution: took branch for data-paper.qmd (complete rewrite), took ours for export_corpus_table.py (has source_count for Unique column)

## Pipeline state

```
catalog_s2        ✅ done (34,055 works)
catalog_merge     ✅ done (71,607 unified)
enrich_works      🔄 running (enrich_dois: 2,269/~30K DOIs resolved)
enrich_embeddings ⏳ waiting
enrich_citations  ⏳ waiting
filter            ⏳ waiting
align             ⏳ waiting
```

## Open questions for author

1. Teaching rebuild: when done, we need another `catalog_merge` pass
2. Old Claude session (pid 395839, from March 20) still alive — should it be killed?
3. PRs #274 and #276 ready for morning review

## Feedback memories saved

- DVC stale lock cleanup procedure (feedback_dvc_locks.md)

## Stale worktrees to clean

- `t252-table2-raw-counts` — likely superseded
- `t257-istex-rebuild` — ISTEX rebuild already merged (#260)
- `t270-s2-source-meta` — PR open
- `t271-s2-datapaper` — PR open
- `/tmp/t270-include-corpus-table` — unknown origin
