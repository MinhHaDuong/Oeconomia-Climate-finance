# Wave 2: Complexity reduction tickets

Red tests: `test_mccabe_complexity` (C901>15), `test_function_length` (PLR0915>80),
`test_branch_count` (PLR0912>15), `test_no_god_modules` (>500L).

Tickets are grouped **by script cluster** (not by ruff rule) to avoid
duplicate refactoring. Each ticket turns multiple violations green at once.
**Archive outputs must remain bit-identical** — verify with `make check`.

---

## Ticket A: Triple-threat god modules (14 violations)

**Scripts:** `refine_flags.py` (684L, 6 violations), `catalog_openalex.py`
(614L, 4), `compare_communities_across_windows.py` (557L, 4)

**Tests turned green (partial):** contributes to all 4 red tests

### Context

These three scripts fail every check: C901, PLR0915, PLR0912, and god-module.
They are the worst offenders and the highest-leverage refactoring targets.

### Relevant files

- `scripts/refine_flags.py` — `_reranker_streaming` (C901=23, PLR0915=113, PLR0912=19), `flag_llm_irrelevant_streaming` (C901=18, PLR0912=17)
- `scripts/catalog_openalex.py` — `main` (C901=24, PLR0915=121, PLR0912=22)
- `scripts/compare_communities_across_windows.py` — `detect_communities` (C901=28, PLR0915=144, PLR0912=23)

### Actions

1. **refine_flags.py**: Extract batch-processing loop from `_reranker_streaming` into `_process_batch()`. Extract prompt construction into `_build_reranker_prompt()`. Extract result parsing into `_parse_reranker_response()`. Split streaming setup from scoring logic in `flag_llm_irrelevant_streaming`.
2. **catalog_openalex.py**: Split `main()` into `fetch_page()`, `process_results()`, `write_incremental()`. Extract budget-guard logic into `check_budget()`. Extract cursor/pagination into a generator.
3. **compare_communities_across_windows.py**: Extract `detect_communities` into `build_graph()`, `run_community_detection()`, `compute_metrics()`. Extract the window-iteration loop into its own function.
4. All three: after function extraction, verify each file is under 500 lines.

### Test

Write no new tests — the existing `test_script_hygiene.py` checks are the acceptance criteria. Run `uv run pytest tests/test_script_hygiene.py -v` to confirm violations decrease.

### Verification

- [ ] `uv run ruff check scripts/refine_flags.py scripts/catalog_openalex.py scripts/compare_communities_across_windows.py --select C901,PLR0915,PLR0912` — zero violations
- [ ] `wc -l` on all three files < 500
- [ ] `make check` passes (all tests + archive bit-invariance)

### Invariants

- Archive outputs bit-identical (same CSVs, same figures)
- All existing tests pass (338+)
- No new dependencies introduced

### Exit criteria

- All 14 violations in these 3 scripts resolved
- All 3 scripts under 500 lines

---

## Ticket B: Complex main functions (18 violations)

**Scripts:** `build_het_core.py` (498L, 3 violations), `calibrate_reranker.py`
(414L, 3), `gen_missing_references.py` (247L, 3), `qa_detect_type.py` (218L, 3),
`export_citation_coverage.py` (81L, 3), `enrich_citations_batch.py` (301L, 3)

**Tests turned green (partial):** contributes to C901, PLR0915, PLR0912

### Context

Six scripts that each fail C901 + PLR0915 + PLR0912 but are not god modules
(all under 500 lines). The fix pattern is uniform: break monolithic `main()` or
single large function into smaller helpers.

### Relevant files

- `scripts/build_het_core.py` — `main` (C901=23, PLR0915=117, PLR0912=22)
- `scripts/calibrate_reranker.py` — `calibrate` (C901=18, PLR0915=136, PLR0912=19)
- `scripts/gen_missing_references.py` — `main` (C901=21, PLR0915=98, PLR0912=22)
- `scripts/qa_detect_type.py` — `classify_type` (C901=21, PLR0915=93, PLR0912=30)
- `scripts/export_citation_coverage.py` — `main` (C901=17, PLR0915=89, PLR0912=19)
- `scripts/enrich_citations_batch.py` — `main` (C901=17, PLR0915=98, PLR0912=17)

### Actions

1. For each script, identify logical blocks inside the large function (data loading, processing, output writing, error handling).
2. Extract each block into a named helper function.
3. `qa_detect_type.py:classify_type` (PLR0912=30, worst branch count): replace if/elif chain with a dispatch dict or lookup table.
4. `calibrate_reranker.py:calibrate` (PLR0915=136, longest function): split into `load_labels()`, `score_candidates()`, `compute_metrics()`, `write_report()`.

### Test

Existing `test_script_hygiene.py` checks. No new tests needed.

### Verification

- [ ] `uv run ruff check <each script> --select C901,PLR0915,PLR0912` — zero violations
- [ ] `make check` passes

### Invariants

- Archive outputs bit-identical
- All existing tests pass

### Exit criteria

- All 18 violations across 6 scripts resolved

---

## Ticket C: Moderate complexity (8 violations)

**Scripts:** `catalog_grey.py` (262L), `catalog_merge.py` (189L),
`qa_word_count.py` (254L), `summarize_core_venues.py` (227L)

**Tests turned green (partial):** contributes to C901, PLR0912

### Context

Four scripts with complex, branchy functions that are not excessively long
(no PLR0915). Fix patterns: dict dispatch for if/elif chains, early returns,
extract branch-heavy logic into helpers.

### Relevant files

- `scripts/catalog_grey.py` — `_query_worldbank_single` (C901=21, PLR0912=21)
- `scripts/catalog_merge.py` — `main` (C901=17, PLR0912=16)
- `scripts/qa_word_count.py` — `main` (C901=17, PLR0912=18)
- `scripts/summarize_core_venues.py` — `canonical_venue` (C901=16, PLR0912=20)

### Actions

1. `catalog_grey.py:_query_worldbank_single`: extract retry/pagination into helper, simplify error-handling branches.
2. `catalog_merge.py:main`: extract each source-merge step into a named function.
3. `qa_word_count.py:main`: extract section-counting logic into `count_sections()`.
4. `summarize_core_venues.py:canonical_venue`: replace if/elif normalization chain with a lookup dict.

### Test

Existing `test_script_hygiene.py` checks.

### Verification

- [ ] `uv run ruff check <each script> --select C901,PLR0912` — zero violations
- [ ] `make check` passes

### Invariants

- Archive outputs bit-identical
- All existing tests pass

### Exit criteria

- All 8 violations across 4 scripts resolved

---

## Ticket D: God modules without function violations (5 modules)

**Scripts:** `collect_syllabi.py` (855L), `analyze_genealogy.py` (798L),
`utils.py` (717L), `analyze_bimodality.py` (673L), `corpus_refine.py` (537L)

**Test turned green:** `test_no_god_modules`

### Context

Five files over 500 lines where no individual function is overly complex — the
problem is module-level sprawl. Splitting requires architectural care, especially
for `utils.py` (imported by every script).

### Relevant files

- `scripts/utils.py` (717L) — imported everywhere; split carefully
- `scripts/collect_syllabi.py` (855L) — longest file in the project
- `scripts/analyze_genealogy.py` (798L) — analysis + visualization mixed
- `scripts/analyze_bimodality.py` (673L) — analysis + visualization mixed
- `scripts/corpus_refine.py` (537L) — orchestrator with inline logic

### Actions

1. **utils.py** (first — dependency of everything): split into `utils.py` (re-exports for backward compat), `utils_retry.py` (retry_get, HTTP helpers), `utils_io.py` (CSV/JSON readers, path helpers), `utils_config.py` (load_analysis_config, load_analysis_periods). Keep `utils.py` as the public interface importing from sub-modules.
2. **collect_syllabi.py**: extract per-university scraping logic into `syllabi_scrapers.py`, keep orchestrator in main file.
3. **analyze_genealogy.py**: extract plotting functions into `plot_genealogy.py`.
4. **analyze_bimodality.py**: extract plotting functions into `plot_bimodality.py`.
5. **corpus_refine.py**: extract flag-application logic (already in refine_flags.py) — review for dead code, inline helpers that can move.

### Test

Existing `test_script_hygiene.py::TestModuleLength::test_no_god_modules`.

### Verification

- [ ] `wc -l` on all 5 files < 500 after split
- [ ] All imports still resolve (no `ImportError`)
- [ ] `make check` passes

### Invariants

- Archive outputs bit-identical
- All existing tests pass
- `from utils import X` continues to work for all X

### Exit criteria

- All 5 modules under 500 lines
- `test_no_god_modules` passes

---

## Ticket E: Minor single-check violations (3 violations)

**Scripts:** `analyze_embeddings.py` (287L), `enrich_abstracts.py` (543L)

**Tests turned green (partial):** contributes to C901, god-module

### Context

Lightest-lift ticket. `analyze_embeddings.py` has one C901 violation barely over
threshold (17 vs 15). `enrich_abstracts.py` has one C901 violation (17) plus
being slightly over the 500-line god-module limit (543L).

### Relevant files

- `scripts/analyze_embeddings.py` — `main` (C901=17)
- `scripts/enrich_abstracts.py` — `step4_semantic_scholar` (C901=17), 543 lines total

### Actions

1. `analyze_embeddings.py:main`: extract one or two helpers (e.g., UMAP config setup, cluster labeling) to drop complexity below 15.
2. `enrich_abstracts.py:step4_semantic_scholar`: extract retry/batch logic into helper. Move one utility function to utils to bring file under 500L.

### Test

Existing `test_script_hygiene.py` checks.

### Verification

- [ ] `uv run ruff check scripts/analyze_embeddings.py scripts/enrich_abstracts.py --select C901` — zero violations
- [ ] `wc -l scripts/enrich_abstracts.py` < 500
- [ ] `make check` passes

### Invariants

- Archive outputs bit-identical
- All existing tests pass

### Exit criteria

- 3 violations resolved
- `enrich_abstracts.py` under 500 lines

---

## Wave plan

**Wave 2a** (parallel): Tickets B + C + E (26 violations, uniform pattern, lower risk)
**Wave 2b**: Ticket A (14 violations, highest complexity, depends on patterns learned in 2a)
**Wave 3**: Ticket D (god-module splits, depends on function-level cleanup settling)

Each wave ends with `make check` (full test suite + archive verification).
