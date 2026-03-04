# Makefile — Counting Climate Finance (Œconomia)
#
# Usage:
#   make            Build manuscript.pdf + manuscript.odt
#   make figures    Regenerate all figures (from existing data)
#   make data       Run slow API collection scripts
#   make clean      Remove build outputs
#   make rebuild    Clean + rebuild everything

# ── Paths ─────────────────────────────────────────────────
# Scripts find data via scripts/utils.py (CLIMATE_FINANCE_DATA env var
# or ~/data/projets/Oeconomia-Climate-finance/).  DATA_DIR here is only
# for Make's timestamp-based dependency tracking.
DATA_DIR    ?= $(HOME)/data/projets/Oeconomia-Climate-finance/catalogs
BIB         := bibliography/main.bib
CSL         := bibliography/oeconomia.csl
SRC         := manuscript.md

REFINED     := $(DATA_DIR)/refined_works.csv
ECON_YEARLY := $(DATA_DIR)/openalex_econ_yearly.csv
OVERLAP     := $(DATA_DIR)/openalex_econ_fin_overlap.csv

# ── Reproducibility ───────────────────────────────────────
# PYTHONHASHSEED=0  → deterministic dict/set iteration order
# SOURCE_DATE_EPOCH=0 → reproducible timestamps in PDF/PNG metadata
export PYTHONHASHSEED := 0
export SOURCE_DATE_EPOCH := 0

# ── Pandoc ────────────────────────────────────────────────
PANDOC_OPTS := --citeproc --bibliography=$(BIB) --csl=$(CSL)

# ── Default target ────────────────────────────────────────
.PHONY: all figures data clean rebuild

all: manuscript.pdf manuscript.odt

# ── Manuscript (Stage 2) ─────────────────────────────────
manuscript.pdf: $(SRC) $(BIB) $(CSL) figures/fig1_emergence.png figures/fig3_alluvial.png
	pandoc $< $(PANDOC_OPTS) --pdf-engine=xelatex -o $@

manuscript.odt: $(SRC) $(BIB) $(CSL) figures/fig1_emergence.png figures/fig3_alluvial.png
	pandoc $< $(PANDOC_OPTS) -o $@

# ── Figures (Stage 1) ────────────────────────────────────
# Fig 1: emergence (economics total + CF share)
figures/fig1_emergence.png: scripts/plot_fig1_emergence.py scripts/plot_helpers.py $(ECON_YEARLY)
	uv run python $< --no-pdf

# Figs 2+3: breakpoints + alluvial (co-produced by one script run)
figures/fig3_alluvial.png figures/fig2_breakpoints.png &: \
		scripts/analyze_alluvial.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Figs 2b+3b: core-only variants (co-produced)
figures/fig3b_alluvial_core.png figures/fig2b_breakpoints_core.png &: \
		scripts/analyze_alluvial.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# Fig 4: citation genealogy (needs bimodality output for pole assignments)
figures/fig4_genealogy.png: scripts/analyze_genealogy.py scripts/utils.py \
		$(REFINED) tables/tab5_pole_papers.csv
	uv run python $< --no-pdf

# Fig 4 alt: PCA seed-axis scatter (core, supervised)
figures/fig4_seed_axis_core.png: scripts/plot_fig45_pca_scatter.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --supervised --no-pdf

# Figs 5a/5b/5c: bimodality tests (co-produced)
figures/fig5a_bimodality.png tables/tab5_pole_papers.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Fig A.1a: robustness (econ vs finance vs RePEc)
figures/figA_1a_robustness.png: scripts/plot_fig1_robustness.py scripts/plot_helpers.py \
		$(ECON_YEARLY) $(OVERLAP)
	uv run python $< --no-pdf

# Aggregate
MANUSCRIPT_FIGS := figures/fig1_emergence.png figures/fig3_alluvial.png
ALL_FIGS := $(MANUSCRIPT_FIGS) \
            figures/fig3b_alluvial_core.png \
            figures/fig4_genealogy.png figures/fig4_seed_axis_core.png \
            figures/fig5a_bimodality.png figures/figA_1a_robustness.png

figures: $(ALL_FIGS)

# ── Data collection (slow — not in default target) ───────
data:
	uv run python scripts/count_openalex_econ_cf.py
	uv run python scripts/count_openalex_econ_cf.py --scope finance
	uv run python scripts/count_openalex_econ_fin_overlap.py
	uv run python scripts/count_repec_econ_cf.py

# ── Housekeeping ─────────────────────────────────────────
clean:
	rm -f manuscript.pdf manuscript.odt

rebuild: clean all
