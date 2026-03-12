# Phase 1 Pipeline Redesign — Issue Handoff Pack

Date: 2026-03-12

## Parent tracker

- #51 — Phase 1 pipeline contract redesign: remove cheap pre-filter and introduce enriched/extended intermediates  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/51

## Sub-issues (TDD-gated)

- #52 — Phase 1 orchestration contract in Makefile (unified -> enriched -> extended -> refined)  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/52
- #53 — Parameterize Phase 1 scripts for configurable works input/output paths  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/53
- #54 — Split corpus_refine into extend mode and filter mode  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/54
- #55 — Deterministic enrichment prioritization with resumable checkpoints  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/55
- #56 — Update docs to canonical Phase 1 artifact contract  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/56
- #57 — Phase 1 migration validation: integration, incrementality, compatibility  
  https://github.com/MinhHaDuong/Oeconomia-Climate-finance/issues/57

## Dependency order

1. #52
2. #53 and #54 (parallel after #52)
3. #55 (after #53)
4. #56 (after #52/#53/#54 stabilize)
5. #57 (last)

## Branch/worktree map (one branch per issue)

- #52 -> `t52-phase1-makefile-contract`
- #53 -> `t53-parameterize-works-paths`
- #54 -> `t54-split-corpus-refine-modes`
- #55 -> `t55-priority-enrichment`
- #56 -> `t56-update-contract-docs`
- #57 -> `t57-phase1-migration-validation`

## Suggested worktree setup

Run from repository root:

```bash
mkdir -p ../worktrees

git worktree add ../worktrees/t52-phase1-makefile-contract -b t52-phase1-makefile-contract
git worktree add ../worktrees/t53-parameterize-works-paths -b t53-parameterize-works-paths
git worktree add ../worktrees/t54-split-corpus-refine-modes -b t54-split-corpus-refine-modes
git worktree add ../worktrees/t55-priority-enrichment -b t55-priority-enrichment
git worktree add ../worktrees/t56-update-contract-docs -b t56-update-contract-docs
git worktree add ../worktrees/t57-phase1-migration-validation -b t57-phase1-migration-validation
```

## Definition of done (applies to all sub-issues)

- Tests first, implementation second, refactor third
- At least one failing test observed before code change
- Add regression tests for all bug fixes
- Deterministic tests; no network dependence without fixtures/mocks
- PR links back to issue and states test plan/results
