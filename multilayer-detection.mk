# multilayer-detection.mk — Figures for the companion paper (ticket 0058)
#
# Four canonical PNGs consumed by content/multilayer-detection.qmd.
#
# Include from the main Makefile:  include multilayer-detection.mk
#
# Targets:
#   companion-figures  — build all four PNGs
#
# Inputs (ticket 0042 rerun outputs; produced by divergence-summary):
#   content/tables/tab_summary_{S2_energy,L1,G9_community,G2_spectral}.csv
#   content/tables/tab_div_C2ST_{embedding,lexical}.csv
#
# Optional inputs (ticket 0056 interpretation layer; stub fallback if absent):
#   content/tables/tab_discrim_terms*.csv
#   content/tables/tab_community_shifts*.csv

COMP_TABLES := content/tables
COMP_FIGS   := content/figures
COMP_CFG    := config/analysis.yaml
COMP_UTILS  := scripts/_companion_plot_utils.py
COMP_STYLE  := scripts/plot_style.py

# Required summary + C2ST inputs (Figures 1 and 2).
COMP_DEPS_CORE := \
    $(COMP_TABLES)/tab_summary_S2_energy.csv \
    $(COMP_TABLES)/tab_summary_L1.csv \
    $(COMP_TABLES)/tab_summary_G9_community.csv \
    $(COMP_TABLES)/tab_summary_G2_spectral.csv \
    $(COMP_TABLES)/tab_div_C2ST_embedding.csv \
    $(COMP_TABLES)/tab_div_C2ST_lexical.csv

# ── Figure 1: Z-score time series ────────────────────────────────────────

$(COMP_FIGS)/fig_companion_zseries.png: \
    scripts/plot_companion_zseries.py $(COMP_UTILS) $(COMP_STYLE) \
    $(COMP_CFG) $(COMP_DEPS_CORE)
	uv run python scripts/plot_companion_zseries.py --output $@

# ── Figure 2: Transition zone heatmap ────────────────────────────────────

$(COMP_FIGS)/fig_companion_heatmap.png: \
    scripts/plot_companion_heatmap.py $(COMP_UTILS) $(COMP_STYLE) \
    $(COMP_CFG) $(COMP_DEPS_CORE)
	uv run python scripts/plot_companion_heatmap.py --output $@

# ── Figure 3: Discriminative terms ───────────────────────────────────────
# No hard dependency on tab_discrim_terms*.csv: the script degrades to a
# TODO(t0064)-annotated stub when the interpretation layer is absent.

$(COMP_FIGS)/fig_companion_terms.png: \
    scripts/plot_companion_terms.py $(COMP_UTILS) $(COMP_STYLE) $(COMP_CFG)
	uv run python scripts/plot_companion_terms.py --output $@

# ── Figure 4: Community shifts ───────────────────────────────────────────
# Same stub-fallback rationale as Figure 3.

$(COMP_FIGS)/fig_companion_community.png: \
    scripts/plot_companion_community.py $(COMP_UTILS) $(COMP_STYLE) $(COMP_CFG)
	uv run python scripts/plot_companion_community.py --output $@

.PHONY: companion-figures
companion-figures: \
    $(COMP_FIGS)/fig_companion_zseries.png \
    $(COMP_FIGS)/fig_companion_heatmap.png \
    $(COMP_FIGS)/fig_companion_terms.png \
    $(COMP_FIGS)/fig_companion_community.png
