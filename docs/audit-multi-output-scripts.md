# Audit: multi-output scripts vs "1 figure = 1 script" guideline

Date: 2026-03-19
Status: diagnostic only (no edits made)

Reference: `docs/local-ai/2026-03-19-memo-harness-extraction.md`, idea #5 — "1 figure = 1 script file. 1 table = 1 script file."

## Method

1. Identified grouped output targets (`&:`) in the Makefile.
2. Scanned Phase 2 scripts for multiple `savefig()` / `save_figure()` / `to_csv()` / `json.dump()` calls writing to distinct output files.
3. Classified each case as **acceptable** (tightly coupled outputs) or **splittable** (independent outputs that could each have their own script).

## Findings

| Script | Outputs | Verdict | Reason |
|--------|---------|---------|--------|
| `compute_vars.py` | `manuscript-vars.yml`, `technical-report-vars.yml`, `data-paper-vars.yml`, `companion-paper-vars.yml` | acceptable | Single computation populates per-document variable subsets from one shared dict. Splitting would duplicate all the stat-gathering logic. |
| `compute_breakpoints.py` | `tab_breakpoints.csv`, `tab_breakpoint_robustness.csv`, `tab_k_sensitivity.csv` (+ core variants via `--core-only`) | **done** (#594) | Refactored: three mutually exclusive modes (`default`, `--robustness`, `--k-sensitivity`), each writing one file to `--output`. |
| `compute_clusters.py` | `tab_alluvial.csv`, `cluster_labels.json`, `tab_core_shares.csv` (+ core variants via `--core-only`) | acceptable | The cluster labels and alluvial cross-tab are joint products of one clustering run. `tab_core_shares.csv` is a filtered view of the same clustering. Splitting would require serializing/deserializing intermediate cluster assignments. |
| `analyze_bimodality.py` | `tab_bimodality.csv`, `tab_axis_detection.csv`, `tab_pole_papers.csv` (+ core variants) | **done** (#550) | Tables-only after split. Three figures moved to `plot_bimodality.py`, `plot_bimodality_lexical.py`, `plot_bimodality_keywords.py`. |
| `analyze_embeddings.py` | `semantic_clusters.csv` | **done** (#551) | Split: `analyze_embeddings.py` produces data only; `plot_semantic.py --color-by {cluster,language,period}` produces one figure per invocation. |
| `analyze_genealogy.py` | `fig_genealogy.png`, `fig_genealogy.html`, `tab_lineages.csv` (+ `tab_louvain_sensitivity.csv` via `--robustness`) | acceptable | The HTML is an interactive companion of the static PNG (same visualization, different format). The lineage table is the data behind the figure. These are tightly coupled. |
| `plot_fig_alluvial.py` | `fig_alluvial.png` | split (#546) | Static PNG renderer. HTML extracted to `plot_alluvial_html.py`. |
| `plot_fig45_pca_scatter.py` | `fig_pca_scatter.png` | **done** | Dropped unconsumed sidecar CSV. |
| `plot_fig_seed_axis.py` | `fig_seed_axis_core.png` | **done** | Dropped unconsumed sidecar CSV. |
| `analyze_cocitation.py` + `plot_cocitation.py` | `communities.csv` / `fig_communities.png` | **done** | Dropped unconsumed sidecar CSVs (summary + sensitivity). Compute script produces `communities.csv` only; plot script reads it. |
| `plot_fig_lexical_tfidf.py` | `fig_lexical_tfidf_{year}.png` (one per detected break year, dynamic) | acceptable | Multiple figures but they share the same logic, parameterized by break year. The dynamic set is inherently co-produced. |

## Summary

- **Total multi-output scripts in Phase 2 pipeline**: 11
- **Acceptable** (tightly coupled outputs): 7
- **Splittable** (independent outputs): 4

### Splittable cases

1. ~~**`analyze_bimodality.py`**~~ — done (#550): split into `analyze_bimodality.py` (tables) + 3 plot scripts.
2. ~~**`analyze_embeddings.py`**~~ — done (#551): split into `analyze_embeddings.py` (data) + `plot_semantic.py` (parameterized plot).
3. ~~**`analyze_cocitation.py`**~~ — done (#552): split into `analyze_cocitation.py` (compute) + `plot_cocitation.py` (figure).

### Notes

- This audit covers Phase 2 scripts only. Phase 1 (corpus building) scripts were excluded — they are DVC-managed and follow different conventions.
- The `save_figure()` utility in `pipeline_io.py` writes PNG by default (add `--pdf` for PDF). PNG+PDF pairs are a single output in two formats, not multi-output.
- Scripts invoked with `--core-only` produce a parallel set of outputs with `_core` suffixes. These are separate Makefile targets calling the same script — acceptable reuse via flags.
- Splitting is a future ticket. This document is diagnostic only.
