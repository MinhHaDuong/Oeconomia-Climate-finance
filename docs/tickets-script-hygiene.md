# Script hygiene alignment tickets

Red tests in `tests/test_script_hygiene.py` define the acceptance criteria.
Each ticket turns one red test green. **Archive outputs must remain bit-identical**
(verify with `make archive-analysis && make -C /tmp/climate-finance-analysis verify`).

---

## Ticket 1: Eliminate sys.path.insert hacks (44 scripts)

**Test:** `TestNoSysPathHacks::test_no_sys_path_insert`

**Problem:** 44 of 63 scripts do `sys.path.insert(0, os.path.dirname(__file__))` to import `utils`. This is the single most repeated boilerplate.

**Fix:** Add `[tool.setuptools.packages.find]` or equivalent to `pyproject.toml` so `scripts/` is an installable package. Then remove all 44 `sys.path.insert` lines and the corresponding `import sys, os` when no longer needed.

**Bit-invariance:** Pure import mechanism change. No output change. Verify archive checksums.

**Scope:** ~44 files, 2-3 lines each + pyproject.toml change.

---

## Ticket 2: Centralize CITE_THRESHOLD in config/analysis.yaml (8 scripts)

**Test:** `TestCentralizedConstants::test_cite_threshold_not_hardcoded`

**Problem:** `CITE_THRESHOLD = 50` is defined independently in 8 scripts:
- analyze_bimodality.py
- analyze_genealogy.py
- compute_clusters.py
- plot_fig45_pca_scatter.py
- plot_fig_alluvial.py
- plot_fig_breakpoints.py
- plot_fig_seed_axis.py
- plot_interactive_corpus.py

The value already exists in `config/analysis.yaml` as `clustering.cite_threshold: 50`.

**Fix:** Replace each `CITE_THRESHOLD = 50` with reading from config:
```python
cfg = load_analysis_config()
CITE_THRESHOLD = cfg["clustering"]["cite_threshold"]
```

**Bit-invariance:** Same value (50), different source. Verify archive checksums.

---

## Ticket 3: Add argparse to 15 entry-point scripts

**Test:** `TestArgparsePresence::test_main_scripts_have_argparse`

**Problem:** 15 scripts with `if __name__ == "__main__"` lack argparse:
analyze_syllabi.py, build_het_core.py, build_teaching_canon.py,
build_teaching_yaml.py, catalog_bibcnrs.py, catalog_grey.py,
catalog_merge.py, catalog_scispsace.py, compute_vars.py,
export_citation_coverage.py, export_corpus_table.py,
gen_missing_references.py, plot_fig_dag.py, qa_word_count.py,
verify_bibliography.py

**Fix:** Add minimal `ArgumentParser()` with `parse_args()`. Use current hardcoded values as defaults. For scripts already in Makefile/DVC, add `--no-pdf` where applicable.

**Bit-invariance:** Adding argparse with same defaults = identical behavior when called without args. Verify archive checksums.

---

## Ticket 4: Reduce McCabe complexity (ruff C901 > 15, 16 functions)

**Test:** `TestFunctionComplexity::test_mccabe_complexity`

**Problem:** 16 functions exceed McCabe complexity 15 (calibrated from ruff default 10 — the 11-14 range is acceptable for sequential research scripts). Worst offenders:
- `collect_syllabi.py:main` (31)
- `catalog_grey.py:_query_worldbank_single` (28)
- `catalog_openalex.py:main` (25)
- `build_het_core.py:main` (23, 24)
- `summarize_core_venues.py:canonical_venue` (21)
- `refine_flags.py:_reranker_streaming` (19)

**Fix:** Extract helper functions. Typical patterns: long if/elif chains → dict dispatch, nested loops → generator functions, mixed setup+logic → separate functions.

**Bit-invariance:** Pure refactoring. Same control flow, same outputs. Verify archive checksums.

---

## Ticket 5: Shorten long functions (ruff PLR0915 > 80, 9 functions)

**Test:** `TestFunctionComplexity::test_function_length`

**Problem:** 9 functions exceed 80 statements (calibrated from ruff default 50 — moderate `main()` functions with sequential setup are acceptable). Worst:
- `build_het_core.py:main` (147)
- `collect_syllabi.py:main` (137)
- `catalog_openalex.py:main` (121, 123)
- `analyze_embeddings.py:main` (123)
- `catalog_grey.py:_query_worldbank_single` (112)

**Fix:** Split monolithic `main()` into pipeline steps. E.g., `main()` calls `load_data()`, `compute_metrics()`, `write_output()`.

**Bit-invariance:** Same pipeline, decomposed. Verify archive checksums.

**Note:** Significant overlap with Ticket 4. Can be worked together.

---

## Ticket 6: Reduce branch count (ruff PLR0912 > 15, 14 functions)

**Test:** `TestFunctionComplexity::test_branch_count`

**Problem:** 14 functions exceed 15 branches (calibrated from ruff default 12). Overlaps heavily with C901 violators. Worst: `qa_detect_type.py:classify_type` (30), `catalog_grey.py:_query_worldbank_single` (29).

**Fix:** Same approach as Ticket 4. Likely resolved as a side effect.

---

## Ticket 7: Split god modules (8 scripts > 500 lines)

**Test:** `TestModuleLength::test_no_god_modules`

**Problem:** 9 scripts exceed 500 lines:
- collect_syllabi.py (856L)
- analyze_genealogy.py (798L)
- utils.py (717L)
- refine_flags.py (687L)
- analyze_bimodality.py (673L)
- catalog_openalex.py (616L)
- compare_communities_across_windows.py (559L)
- enrich_abstracts.py (544L)
- corpus_refine.py (539L)

**Fix priority:** Start with `utils.py` → split into `utils_retry.py`, `utils_io.py`, `utils_paths.py`. Then tackle analysis scripts by extracting reusable functions.

**Bit-invariance:** Module splitting is pure refactoring. Verify archive checksums.

---

## Wave plan

Tickets 1-3 are mechanical (low risk, high reward). Tickets 4-7 overlap and require judgment. Suggested waves:

**Wave 1:** Tickets 1 + 2 + 3 (boilerplate removal, can parallelize)
**Wave 2:** Tickets 4 + 5 + 6 (complexity reduction, work together per script)
**Wave 3:** Ticket 7 (module splitting, depends on wave 2 settling)

Each wave ends with `make archive-analysis` + checksum verification.
