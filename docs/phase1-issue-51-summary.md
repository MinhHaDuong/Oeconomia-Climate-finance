# #51 Implementation Summary

## Objective
Redesign Phase 1 pipeline contract to support resumable enrichment and deterministic ordering.

## Status
✅ **Complete** — All 6 sub-issues implemented, tested, and pushed to GitHub.

## Sub-issue PRs

| Ticket | PR | Branch | Status | Tests |
|--------|----|---------| ---------|-------|
| #52 | #58 | `t52-phase1-makefile-contract` | ✅ Pushed | 13 pass |
| #53 | #59 | `t53-parameterize-works-paths` | ✅ Pushed | 16 pass |
| #54 | #60 | `t54-split-corpus-refine-modes` | ✅ Pushed | 48 pass |
| #55 | #61 | `t55-priority-enrichment` | ✅ Pushed | 47 pass |
| #56 | #62 | `t56-update-contract-docs` | ✅ Pushed | 48 pass |
| #57 | #63 | `t57-phase1-migration-validation` | ✅ Pushed | 42 pass |

## Key Changes

### Phase 1 Pipeline (Now 4 Steps)

```
7 sources ──→ merge ──→ unified_works.csv      [corpus-discover]
                             │
                             ▼
                        enrich enrichment        [corpus-enrich]
                             │
                             ▼
                        enriched_works.csv
                             │
                             ▼
                        flag all works           [corpus-extend]
                        (add flags, no row drop)
                             │
                             ▼
                        extended_works.csv
                             │
                             ▼
                        apply policy → filter   [corpus-filter]
                             │
                             ▼
                        refined_works.csv (Phase 1 output)
```

### Key Artifacts

- `unified_works.csv` — deduplicated merge output (Phase 1a)
- `enriched_works.csv` — after DOI/abstract/citation enrichment (Phase 1b)
- `extended_works.csv` — all works with quality flags computed (Phase 1c)
- `refined_works.csv` — final output after policy filter (Phase 1d)

### Implementation Highlights

1. **Makefile Contract (#52)**
   - Four explicit targets: `corpus-discover`, `corpus-enrich`, `corpus-extend`, `corpus-filter`
   - Fail-fast checks ensure inputs exist before running
   - Removed incorrect `--cheap` pre-filter from `corpus-discover`

2. **Scriptable Paths (#53)**
   - All enrichment scripts accept `--works-input` and `--works-output` options
   - Enables chaining: `unified` → `enrich` → `enriched` → `flag` → `extend` → `filter` → `refined`
   - Backward compatible defaults (e.g., `--works-input refined_works.csv`)

3. **Split Corpus Refine Modes (#54)**
   - `--extend` mode: reads enriched, computes flags on all rows, writes extended (no row drop)
   - `--filter` mode: reads extended (with flags), applies policy, writes refined + audit
   - `--apply` preserved as backward-compat alias (reads `unified`, runs extend+filter chain)

4. **Deterministic Priority (#55)**
   - `compute_priority_scores()` and `sort_dois_by_priority()` in `utils.py`
   - Citation enrichment scripts process DOIs in descending priority order (high citation count first)
   - Same input → same processing order (deterministic; enables reproducible budget-capped runs)

5. **Documentation (#56)**
   - Updated AGENTS.md, README.md, corpus-construction.md, reproducibility.md
   - Canonical four-step pipeline definition consistent across docs
   - Removed stale "cheap filter before enrichment" narrative

6. **Migration Validation (#57)**
   - Integration tests: Phase 1 producing valid outputs on sample data
   - Idempotency: `corpus_refine --apply` produces same result on rerun
   - Backward compatibility: old `--apply` flag and checkpoints still work
   - Contract validation: refined_works.csv schema, embeddings.npz format

## Test Results

- **Total new tests**: ~40 across all 6 branches
- **Total tests in repo**: 180+ (including existing test suite)
- **All passing**: ✅

## Next Steps (for Author Review)

1. **Review & merge each PR in order**:
   - #58 (Makefile) — foundation
   - #59 (parameters) — enables #60
   - #60 (split modes) — core refactoring
   - #61 (priority) — optional extension, doesn't block
   - #62 (docs) — reference documentation
   - #63 (migration) — validation and safety checks

2. **Integration testing**: Build the pipeline end-to-end on sample data after merging all 6

3. **Close #51** once all 6 PRs are merged

## Breaking Changes & Migration

- **Breaking**: `corpus_refine.py` now has `--extend`/`--filter` modes (but `--apply` works as before)
- **Breaking**: Enrich scripts now read from `unified_works.csv` by default (was `refined_works.csv`)
- **Migration path**: `--apply` alias ensures old Makefile targets still work; can be removed in v2

## Reproducibility

- All scripts support `--help` documenting new args
- Phase 1 → Phase 2 contract remains: `refined_works.csv`, `embeddings.npz`, `citations.csv`
- Checkpoint files (`.citations_batch_checkpoint.csv`) compatible and preserved

## Deployment Checklist

- [ ] Review all 6 PRs (in order)
- [ ] Merge all 6 PRs to `main`
- [ ] Run `make corpus` on real data to verify end-to-end
- [ ] Close #51 with reference to merged PRs
- [ ] Tag release (if applicable)

---

**Created by AI assistant (GitHub Copilot) on 2026-03-11**  
**TDD workflow: all tests written first, all passing before merge**
