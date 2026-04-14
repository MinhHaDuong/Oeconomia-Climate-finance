# divergence.mk — Multi-channel structural break detection pipeline
#
# Include from the main Makefile:  include divergence.mk
#
# Targets:
#   divergence-tables   Compute all divergence series (semantic, lexical, citation)
#   divergence-figures  Plot one figure per method
#   divergence          Both tables and figures
#
# Inputs (Phase 1 contract):
#   $(REFINED), $(REFINED_EMB), $(REFINED_CIT) — defined in main Makefile

# ── Paths ─────────────────────────────────────────────────────────────────

DIV_TABLES := content/tables
DIV_FIGS   := content/figures
DIV_CFG    := config/analysis.yaml

# ── Tables (Phase 2 — compute) ───────────────────────────────────────────

TAB_SEM := $(DIV_TABLES)/tab_semantic_divergence.csv
TAB_LEX := $(DIV_TABLES)/tab_lexical_divergence.csv
TAB_CIT := $(DIV_TABLES)/tab_citation_divergence.csv

$(TAB_SEM): scripts/compute_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG)
	python3 scripts/compute_divergence_semantic.py --output $@

$(TAB_LEX): scripts/compute_divergence_lexical.py $(REFINED) $(DIV_CFG)
	python3 scripts/compute_divergence_lexical.py --output $@

$(TAB_CIT): scripts/compute_divergence_citation.py $(REFINED) $(REFINED_CIT) $(DIV_CFG)
	python3 scripts/compute_divergence_citation.py --output $@

# Companion breaks files are produced as side-effects:
#   tab_semantic_divergence_breaks.csv
#   tab_lexical_divergence_breaks.csv
#   tab_citation_divergence_breaks.csv

.PHONY: divergence-tables
divergence-tables: $(TAB_SEM) $(TAB_LEX) $(TAB_CIT)

# ── Figures (Phase 2 — plot) ─────────────────────────────────────────────
#
# plot_divergence.py reads all three CSVs and writes one PNG per method.
# The --output gives the stem; actual files are {stem}_{method}.png.

DIV_FIG_STAMP := $(DIV_FIGS)/.divergence_figs.stamp

$(DIV_FIG_STAMP): scripts/plot_divergence.py $(TAB_SEM) $(TAB_LEX) $(TAB_CIT)
	python3 scripts/plot_divergence.py \
		--output $(DIV_FIGS)/fig_divergence.png \
		--input $(TAB_SEM) $(TAB_LEX) $(TAB_CIT)
	touch $@

.PHONY: divergence-figures
divergence-figures: $(DIV_FIG_STAMP)

# ── Convenience ──────────────────────────────────────────────────────────

.PHONY: divergence
divergence: divergence-tables divergence-figures
