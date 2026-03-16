# State

Last updated: 2026-03-16

## Manuscript

- ~9,600 words (target ~9,000), 61 bib entries
- 3 figures (emergence, breakpoints, alluvial) + 2 tables (traditions, poles)
- Variable dependencies reduced to 1 (`corpus_total_approx`)
- Phase 2→3 contract documented in manuscript.qmd header comment
- ΔBIC values, cluster counts, language % moved out of prose (belong in companion)

## Corpus

- 27,534 refined works (from 35,143 unified), embeddings + citations cached
- Schema normalized: `from_openalex`, `from_s2`, ..., `from_teaching` boolean columns (1NF)
- DVC-managed: `dvc.yaml` (6 stages), `dvc.lock` committed, remote padme in sync
- DVC cache external: `/home/haduong/data/projets/.../dvc-cache` (hors Nextcloud)
- Validation: `make corpus-validate` 42 passed, 1 pre-existing failure (duplicate DOIs)
- `make check-fast`: 194 passed, 0 failures
- Ecology filter tightened and corpus regenerated

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992
- Fig 2 (composition): relocated to §3.4 (thematic decomposition argument)
- Fig S1 (traditions): co-citation network, color, Electronic Supplement (PR #88 merged)
- Table 2 (poles): efficiency vs accountability terms — done
- Table 1 (traditions): caption updated; §1.5 cites co-citation evidence (Q=0.68)

## Blockers

None.

## Active PRs

None.

## Recent

- **AGENTS.md restructured** (#142, #145, 2026-03-16): Dragon Dreaming phase awareness (Doing runs in fresh context), DD/TDD heading hierarchy fixed, autonomous workflow rewritten as iterative wave cycle, escalation policy added.
- **Unified trigger system** (#140, 2026-03-16): scattered runbook references replaced with Triggers table in AGENTS.md. Hooks renamed to Triggers to avoid git-hooks confusion.
- **catalog_bibcnrs as DVC stage** (#134, 2026-03-15): `catalog_bibcnrs` stage added to `dvc.yaml`; `data/exports/` tracked via `data/exports.dvc`.
- **DVC chantier complete** (2026-03-15): 10 tickets, data versioned with DVC, pipeline DAG, external cache, bidirectional push/pull doudou ↔ padme.
- **Test infra complete** (#117–#123, #129–#130): `make check-fast` 194 passed, 0 failures.

## Open tickets

- #135: Fix teaching source pipeline (add generation script, move yaml to data/, DVC-track syllabi)
- #96: Document seed axis PCA decomposition in companion paper
- #26: Human proofread of full manuscript

## Next priorities

1. Human proofread of full manuscript (#26)
2. Fix teaching source pipeline (#135)
3. Regen period detection curves + terms table for §2.5
4. Move ΔBIC details + cluster counts to companion paper (#96)
