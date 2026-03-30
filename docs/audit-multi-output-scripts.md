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
| `compute_breakpoints.py` | `tab_breakpoints.csv`, `tab_breakpoint_robustness.csv` (+ core variants via `--core-only`, + `tab_k_sensitivity.csv` via `--robustness`) | acceptable | Robustness table is derived from the breakpoint detection in the same run. The k-sensitivity table is gated behind a `--robustness` flag — a separate entry point in the Makefile already exists. Core variants use `--core-only`. |
| `compute_clusters.py` | `tab_alluvial.csv`, `cluster_labels.json`, `tab_core_shares.csv` (+ core variants via `--core-only`) | acceptable | The cluster labels and alluvial cross-tab are joint products of one clustering run. `tab_core_shares.csv` is a filtered view of the same clustering. Splitting would require serializing/deserializing intermediate cluster assignments. |
| `analyze_bimodality.py` | `fig_bimodality.png`, `fig_bimodality_lexical.png`, `fig_bimodality_keywords.png`, `tab_bimodality.csv`, `tab_axis_detection.csv`, `tab_pole_papers.csv` (+ core variants) | **splittable** | Three independent figures (embedding histogram, lexical histogram, keyword scatter) plus three tables. The figures visualize different aspects and could be separate plotting scripts reading the tables. The tables themselves are tightly coupled (single analysis run), but the figures are not. |
| `analyze_embeddings.py` | `fig_semantic.png`, `fig_semantic_lang.png`, `fig_semantic_period.png`, `semantic_clusters.csv` | **splittable** | Three figures color the same UMAP by different variables (cluster, language, period). Each is an independent visualization that could be its own script reading pre-computed UMAP coordinates. The CSV of cluster assignments is a data product, not a figure. |
| `analyze_genealogy.py` | `fig_genealogy.png`, `fig_genealogy.html`, `tab_lineages.csv` (+ `tab_louvain_sensitivity.csv` via `--robustness`) | acceptable | The HTML is an interactive companion of the static PNG (same visualization, different format). The lineage table is the data behind the figure. These are tightly coupled. |
| `plot_fig_alluvial.py` | `fig_alluvial.png`, `fig_alluvial.html` | acceptable | HTML is an interactive companion of the static figure (same visualization, two formats). |
| `plot_fig45_pca_scatter.py` | `fig_pca_scatter.png`, `tab_pca_axes.csv` | acceptable | The CSV records axis metadata for the figure — a sidecar, not an independent product. |
| `plot_fig_seed_axis.py` | `fig_seed_axis_core.png`, `tab_seed_axis_core.csv` | acceptable | Same pattern — CSV is a sidecar table for the figure. |
| `analyze_cocitation.py` | `communities.csv`, `tab_community_summary.csv`, `fig_communities.png` | **splittable** | Not in the Makefile (no target), but the script produces a data table, a summary table, and a figure — three independent outputs. The community detection (data) and the network visualization (figure) are separable. |
| `plot_fig_lexical_tfidf.py` | `fig_lexical_tfidf_{year}.png` (one per detected break year, dynamic) | acceptable | Multiple figures but they share the same logic, parameterized by break year. The dynamic set is inherently co-produced. |

## Summary

- **Total multi-output scripts in Phase 2 pipeline**: 11
- **Acceptable** (tightly coupled outputs): 8
- **Splittable** (independent outputs): 3

### Splittable cases

1. **`analyze_bimodality.py`** — 3 independent figures + 3 tables. The tables are one analysis; each figure could be a separate plot script.
2. **`analyze_embeddings.py`** — 3 independent UMAP figures + 1 CSV. Each figure colors by a different variable; trivially separable if UMAP coordinates are saved first.
3. **`analyze_cocitation.py`** — community detection + summary table + network figure. Not in Makefile yet; when added, should be split.

### Notes

- This audit covers Phase 2 scripts only. Phase 1 (corpus building) scripts were excluded — they are DVC-managed and follow different conventions.
- The `save_figure()` utility in `pipeline_io.py` writes PNG by default (opt-in PDF with `--pdf`). PNG+PDF pairs are a single output in two formats, not multi-output.
- Scripts invoked with `--core-only` produce a parallel set of outputs with `_core` suffixes. These are separate Makefile targets calling the same script — acceptable reuse via flags.
- Splitting is a future ticket. This document is diagnostic only.
