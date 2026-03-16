# State

Last updated: 2026-03-16

## Manuscript

- ~9,600 words (target ~9,000), 61 bib entries
- 2 figures (emergence, composition) + 3 tables (traditions, poles, venues) + 1 supplement figure (seed axis)
- Variable dependencies reduced to 1 (`corpus_total_approx`)

## Corpus

- 27,534 refined works (from 35,143 unified), embeddings + citations cached
- Schema normalized: `from_openalex`, `from_s2`, ..., `from_teaching` boolean columns (1NF)
- DVC-managed: `dvc.yaml` (6 stages), `dvc.lock` committed, remote padme in sync
- DVC cache external: `/home/haduong/data/projets/.../dvc-cache` (hors Nextcloud)
- Validation: `make corpus-validate` 42 passed, 1 pre-existing failure (duplicate DOIs)
- `make check-fast`: 229 passed, 0 failures

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992
- Fig 2 (composition): relocated to §3.4 (thematic decomposition argument)
- Fig S1 (traditions): co-citation network, color, Electronic Supplement (PR #88 merged)
- Fig S2 (seed axis): efficiency–accountability scatter, Electronic Supplement (#150, #151)
- Table 1 (traditions): caption updated; §1.5 cites co-citation evidence (Q=0.68)
- Table 2 (venues): 17 journals by pole lean, replaces @fig-seed in body (#150, #151)
- Table (poles): efficiency vs accountability terms — in companion paper

## Blockers

None.

## Active PRs

None.

## Recent

- **Venue table replaces fig-seed** (#150, #151, 2026-03-16): @tbl-venues (17 journals by pole lean) in §3.4 body; @fig-seed moved to Electronic Supplement. Makefile rule added. 8 tests.
- **Companion paper complete draft** (#149, 2026-03-16): all [TO WRITE] sections filled. §2 lit review (22 bib entries), §5.1–5.2 results, §6 restructured, §7 conclusion. 27 content tests. §4 Method remains as technical-report includes (editorial pass needed before submission).
- **Companion paper §5.3–5.4** (#96, #147, 2026-03-16): bimodality results + PCA decomposition prose written, erratum on earlier values, 9 content tests added.
- **AGENTS.md restructured** (#142, #145, 2026-03-16): Dragon Dreaming phase awareness (Doing runs in fresh context), DD/TDD heading hierarchy fixed, autonomous workflow rewritten as iterative wave cycle, escalation policy added.
- **Unified trigger system** (#140, 2026-03-16): scattered runbook references replaced with Triggers table in AGENTS.md. Hooks renamed to Triggers to avoid git-hooks confusion.
- **catalog_bibcnrs as DVC stage** (#134, 2026-03-15): `catalog_bibcnrs` stage added to `dvc.yaml`; `data/exports/` tracked via `data/exports.dvc`.
- **DVC chantier complete** (2026-03-15): 10 tickets, data versioned with DVC, pipeline DAG, external cache, bidirectional push/pull doudou ↔ padme.
- **Test infra complete** (#117–#123, #129–#130): `make check-fast` 194 passed, 0 failures.

## Open tickets

- #135: Fix teaching source pipeline (add generation script, move yaml to data/, DVC-track syllabi)
- #26: Human proofread of full manuscript

