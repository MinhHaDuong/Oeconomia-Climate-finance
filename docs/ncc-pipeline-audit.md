# NCC Pipeline Audit

Assessment of codebase and Makefile readiness for a Nature Climate Change
"Analysis" piece (~2,000 words, 4 figures).

Date: 2026-04-13

## 1. Figure-to-Script Mapping

The NCC piece needs four figures. Here is what exists and what is missing.

### (a) Sliding-window divergence showing 2009 peak

**Need:** A figure showing the censored-gap k=2 result where the single
surviving breakpoint is at 2009. The current figures show baseline k=0.

**Existing scripts:**
- `scripts/compute_breakpoints.py` -- supports `--censor-gap N` flag.
  Produces `tab_breakpoints.csv` (and censor variants).
- `scripts/plot_fig_breakpoints.py` -- supports `--censor-gap N` flag.
  Reads the censor-variant CSV and renders the figure.
- `scripts/plot_fig2_breaks.py` -- simpler two-metric view (JS + cosine,
  w=3 only). Does NOT support censor-gap; reads only baseline CSV.

**Existing Makefile targets:**
- `content/figures/fig_breakpoints.png` -- baseline (k=0), full corpus.
- `content/figures/fig_breaks.png` -- simplified two-metric view (k=0).
- `content/figures/fig_breakpoints_core.png` -- baseline (k=0), core.
- No target for censor-gap variants.
- No censor-gap figure files currently exist in `content/figures/`.

**What is needed:**
1. New Makefile targets for censor-gap tables:
   `content/tables/tab_breakpoints_censor2.csv` and
   `content/tables/tab_breakpoint_robustness_censor2.csv`.
2. New Makefile target for the NCC divergence figure, e.g.,
   `content/figures/fig_breakpoints_censor2.png`.
3. Alternatively, a new NCC-specific plot script that overlays k=0
   and k=2 curves to show the convergence on 2009. This may be
   better for a 2,000-word piece aimed at a policy audience.

### (b) Core vs. full corpus comparison

**Need:** A figure showing that the core subset has no structural break
while the full corpus does.

**Existing assets:**
- `content/_includes/core-vs-full.md` -- prose text with `{{< meta >}}`
  variables. Not a figure.
- `content/figures/fig_breakpoints.png` (full corpus) and
  `content/figures/fig_breakpoints_core.png` (core) exist as separate
  PNGs.

**What is needed:**
- A new composite figure (panel a = full corpus, panel b = core) or
  a single multi-panel plot. No existing script produces this.
- New plot script, e.g., `scripts/plot_ncc_core_comparison.py`, that
  reads both `tab_breakpoints.csv` and `tab_breakpoints_core.csv` and
  renders a side-by-side panel figure.
- New Makefile target for the composite figure.

### (c) Efficiency-accountability bimodality KDE

**Need:** KDE showing the bimodal distribution along the seed axis.

**Existing scripts and figures:**
- `scripts/plot_figS_kde.py` -- grayscale KDE with GMM overlay, reads
  `tab_pole_papers.csv`. Produces `content/figures/fig_kde.png`. This is
  the closest match. Currently a supplement figure, not period-decomposed.
- `scripts/plot_bimodality.py` -- KDE by period (3 panels: pre-2007,
  2007-2014, 2015-2024) with GMM overlay. Produces
  `content/figures/fig_bimodality.png`.

**Existing Makefile targets:**
- `content/figures/fig_kde.png` -- target exists, uses `plot_figS_kde.py`.
- `content/figures/fig_bimodality.png` -- target exists, uses
  `plot_bimodality.py`.

**Assessment:**
- `fig_kde.png` could serve the NCC piece directly or with minor
  adaptation (add period decomposition, adjust dimensions).
- `fig_bimodality.png` is already period-decomposed and shows the
  temporal emergence of bimodality. Probably the better choice for
  the NCC argument about categories crystallizing.
- May need an NCC-specific variant that combines both (overall KDE +
  period breakdown) into a compact panel figure.

### (d) Alluvial diagram showing stable cluster structure

**Need:** Alluvial showing thematic flows across three periods, emphasizing
stability.

**Existing scripts and figures:**
- `scripts/plot_fig_alluvial.py` -- renders static PNG. Supports
  `--core-only`. Produces `content/figures/fig_alluvial.png`.
- `content/figures/fig_alluvial.png` -- exists, full corpus.
- `content/figures/fig_alluvial_core.png` -- exists, core subset.

**Existing Makefile targets:**
- Both figures have targets (lines 338-341 and 414-417).

**Assessment:**
- `fig_alluvial.png` is likely usable as-is or with minor cosmetic
  adjustments (NCC dimensions, font sizes).
- No new script needed unless NCC format requires different sizing.


## 2. Makefile Changes Needed

### New intermediate targets (Phase 2 tables)

```makefile
# Censor-gap k=2 breakpoints (NCC figure a)
content/tables/tab_breakpoints_censor2.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	uv run python $< --output $@ --censor-gap 2

content/tables/tab_breakpoint_robustness_censor2.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	uv run python $< --output $@ --robustness --censor-gap 2
```

### New figure targets

```makefile
# NCC-specific figures
NCC_FIGS := content/figures/fig_ncc_divergence.png \
            content/figures/fig_ncc_core_comparison.png \
            content/figures/fig_ncc_bimodality.png \
            content/figures/fig_ncc_alluvial.png

# Or reuse existing figures with NCC-format wrappers
```

The exact targets depend on the decision in ticket 0018 (adapt existing
scripts vs. write new NCC-specific ones). The scripts already support
the underlying computations; the question is presentation format.

### New document target

```makefile
NCC_INCLUDES := (TBD -- likely minimal or none)

output/content/ncc-analysis.pdf: content/ncc-analysis.qmd $(BIB) $(NCC_FIGS) \
        $(PROJECT_INCLUDES) content/ncc-analysis-vars.yml
	quarto render $< --to pdf
```

Update `papers` target:
```makefile
papers: check-corpus output/content/technical-report.pdf \
        output/content/data-paper.pdf output/content/companion-paper.pdf \
        output/content/ncc-analysis.pdf
```

### compute_vars.py update

Add an `"ncc-analysis"` entry to the `DOC_VARS` dictionary in
`scripts/compute_vars.py` (around line 113). The NCC piece would need a
subset of companion-paper variables, likely:
- `corpus_total`, `corpus_total_approx`, `corpus_core`,
  `corpus_core_threshold`, `corpus_sources`
- `bim_dbic_embedding`, `bim_dbic_tfidf`, `bim_corr`
- `bim_dbic_post2015`, `bim_dbic_2007_2014`
- `analysis_corpus_n`

### _quarto.yml update

Add `content/ncc-analysis.qmd` to the render list:
```yaml
render:
  - content/manuscript.qmd
  - content/technical-report.qmd
  - content/data-paper.qmd
  - content/companion-paper.qmd
  - content/ncc-analysis.qmd
```

### PHONY and ALL_FIGS updates

Add `figures-ncc` to `.PHONY` and `NCC_FIGS` to `ALL_FIGS`.


## 3. Architecture Recommendation

**Recommendation: 5th Quarto document in `content/`.**

Rationale:
- The project already manages 4 Quarto outputs sharing includes and a
  common bibliography. Adding a 5th follows the established pattern.
- The Makefile already has per-document namespacing (figure sets, include
  sets, vars files, render targets). Extending this is straightforward.
- The `PROJECT_INCLUDES` variable ensures all includes resolve for every
  render. Adding NCC includes to this set is one line.
- `compute_vars.py` already supports per-document variable selection.
  Adding an NCC entry is ~10 lines.
- A standalone file outside the Quarto project would lose `{{< meta >}}`
  variable injection, shared bibliography, and CSL formatting.

**Recommended file:** `content/ncc-analysis.qmd`

**The NCC piece should NOT reuse `{{< include >}}` directives** from the
technical report or companion paper. At ~2,000 words, the NCC text must
be original prose tailored to a policy audience. The includes are written
for a methods audience. Instead, the NCC document should reference figures
directly and contain self-standing prose.


## 4. Variables the NCC Piece Would Need

Based on the companion paper's usage and the NCC argument structure:

| Variable | Current value | Used for |
|----------|---------------|----------|
| `corpus_total` | 31,713 | Corpus size statement |
| `corpus_total_approx` | 32,000 | Round number for abstract |
| `corpus_core` | 2,648 | Core subset size |
| `corpus_core_threshold` | 50 | Citation threshold |
| `corpus_sources` | 6 | Number of sources |
| `analysis_corpus_n` | 28,015 | Analysis corpus (with embeddings) |
| `bim_dbic_embedding` | 1,255 | Bimodality strength |
| `bim_dbic_tfidf` | 15,345 | Lexical validation strength |
| `bim_corr` | 0.77 | Cross-validation correlation |
| `bim_dbic_2007_2014` | -44 | Unimodal during crystallization |
| `bim_dbic_post2015` | 951 | Bimodal after 2015 |
| `emb_dimensions` | 1024 | Brief methods note |

These are all already computed by `compute_vars.py`. No new computation
needed -- just a new entry in `DOC_VARS` selecting the subset.


## 5. What Companion Paper Build Depends On

The target `output/content/companion-paper.pdf` depends on:
- `content/companion-paper.qmd`
- `$(PROJECT_INCLUDES)` -- all includes from all documents (Quarto resolves
  cross-document references)
- `$(BIB)` -- `content/bibliography/main.bib`
- `content/companion-paper-vars.yml` -- auto-generated by `compute_vars.py`

The vars file in turn depends on (via the grouped `$(COMPUTED_STATS)` target):
- `scripts/compute_vars.py`, `scripts/utils.py`
- `$(REFINED)` -- `data/catalogs/refined_works.csv`
- `content/tables/tab_bimodality.csv`, `tab_bimodality_core.csv`,
  `tab_axis_detection.csv`
- Various optional files (unified, audit, embeddings, citations, QA report)

Note: The companion paper's Makefile target does NOT list its figures as
prerequisites. The figures (`COMPANION_FIGS`) are only pulled in by the
`figures-companion` target. This means `make output/content/companion-paper.pdf`
will render even if figures are stale or missing -- Quarto will embed
whatever PNGs exist at render time. This is a known design choice (figures
are pre-built, not rebuilt on every render).


## 6. Reorganization Needed Before Execution

### Must-do (blocking)

1. **No censor-gap Makefile targets.** The NCC's primary figure (divergence
   showing 2009) requires censor-gap k=2 tables and figures. Scripts support
   it but no targets exist. Must add before ticket 0018 can execute.

2. **No composite core-vs-full figure script.** Figure (b) requires a new
   script that combines full and core breakpoints into one panel. The data
   exists; the visualization does not.

### Should-do (recommended)

3. **Add NCC entry to compute_vars.py `DOC_VARS`.** Otherwise the NCC
   document cannot use `{{< meta >}}` variables. ~10 lines.

4. **Add ncc-analysis.qmd to _quarto.yml.** Required for Quarto to render
   the document.

5. **Decide on figure naming convention.** Either `fig_ncc_*.png` (new
   NCC-specific figures) or reuse existing figure filenames with NCC
   format parameterization. Recommendation: new `fig_ncc_*.png` files to
   avoid disturbing existing documents' figures.

### Nice-to-have (can defer)

6. **The structural-breaks.md include has a stale note** (lines 60-63)
   about z-scores recomputed from an earlier corpus version where 2013
   no longer meets robustness. The author should resolve this before the
   companion paper is posted as preprint (ticket 0015 scope).

7. **core-vs-full.md include references `compute_alluvial.py`** (line 17)
   but the actual script is `compute_clusters.py`. Stale reference.


## 7. Summary of Required New Files

| File | Purpose |
|------|---------|
| `content/ncc-analysis.qmd` | Main NCC document |
| `content/ncc-analysis-vars.yml` | Auto-generated vars (add to compute_vars.py) |
| `scripts/plot_ncc_divergence.py` | Figure (a): divergence with 2009 peak |
| `scripts/plot_ncc_core_comparison.py` | Figure (b): full vs core panel |
| 2 new Makefile targets for censor-gap tables | Intermediate data |
| 4 new Makefile targets for NCC figures | Build targets |
| 1 new Makefile target for NCC PDF | Render target |

Figures (c) and (d) may reuse existing scripts (`plot_figS_kde.py` or
`plot_bimodality.py` for KDE; `plot_fig_alluvial.py` for alluvial) with
NCC-specific parameterization or minor wrappers.
