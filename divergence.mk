# divergence.mk — Multi-channel structural break detection pipeline
#
# Include from the main Makefile:  include divergence.mk
#
# Architecture: one CSV per method via scripts/compute_divergence.py --method X
#
# Targets:
#   divergence-semantic  Compute semantic methods (S1-S4)
#   divergence-lexical   Compute lexical methods (L1-L3)
#   divergence-citation  Compute citation methods (G1-G8)
#   divergence-tables    All 15 divergence CSVs
#   divergence-figures   Plot one figure per method
#   divergence           Both tables and figures
#
# Inputs (Phase 1 contract):
#   $(REFINED), $(REFINED_EMB), $(REFINED_CIT) — defined in main Makefile

# ── Paths ─────────────────────────────────────────────────────────────────

DIV_TABLES := content/tables
DIV_FIGS   := content/figures
DIV_CFG    := config/analysis.yaml
DIV_DISPATCH := scripts/compute_divergence.py

# ── Method lists ─────────────────────────────────────────────────────────

DIV_METHODS_SEM := S1_MMD S2_energy S3_sliced_wasserstein S4_frechet
DIV_METHODS_LEX := L1 L2 L3
DIV_METHODS_CIT := G1_pagerank G2_spectral G3_coupling_age G4_cross_tradition \
                   G5_pref_attachment G6_entropy G7_disruption G8_betweenness

# ── Derived file lists ───────────────────────────────────────────────────

DIV_CSV_SEM := $(foreach m,$(DIV_METHODS_SEM),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_LEX := $(foreach m,$(DIV_METHODS_LEX),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_CIT := $(foreach m,$(DIV_METHODS_CIT),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_ALL := $(DIV_CSV_SEM) $(DIV_CSV_LEX) $(DIV_CSV_CIT)

# ── Semantic methods (depend on embeddings) ──────────────────────────────

$(foreach m,$(DIV_METHODS_SEM),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	python3 $(DIV_DISPATCH) --method $(m) --output $$@))

# ── Lexical methods (depend on REFINED only) ─────────────────────────────

$(foreach m,$(DIV_METHODS_LEX),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_lexical.py $(REFINED) $(DIV_CFG) ; \
	python3 $(DIV_DISPATCH) --method $(m) --output $$@))

# ── Citation methods (depend on REFINED + REFINED_CIT) ───────────────────

$(foreach m,$(DIV_METHODS_CIT),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_citation.py $(REFINED) $(REFINED_CIT) $(DIV_CFG) ; \
	python3 $(DIV_DISPATCH) --method $(m) --output $$@))

# ── Convenience targets ──────────────────────────────────────────────────

.PHONY: divergence-semantic
divergence-semantic: $(DIV_CSV_SEM)

.PHONY: divergence-lexical
divergence-lexical: $(DIV_CSV_LEX)

.PHONY: divergence-citation
divergence-citation: $(DIV_CSV_CIT)

.PHONY: divergence-tables
divergence-tables: $(DIV_CSV_ALL)

# ── Figures (Phase 2 — plot) ─────────────────────────────────────────────
#
# plot_divergence.py reads the individual CSVs and writes one PNG per method.
# The --output gives the stem; actual files are {stem}_{method}.png.

DIV_FIG_STAMP := $(DIV_FIGS)/.divergence_figs.stamp

$(DIV_FIG_STAMP): scripts/plot_divergence.py $(DIV_CSV_ALL)
	python3 scripts/plot_divergence.py \
		--output $(DIV_FIGS)/fig_divergence.png \
		--input $(DIV_CSV_ALL)
	touch $@

.PHONY: divergence-figures
divergence-figures: $(DIV_FIG_STAMP)

# ── Top-level ────────────────────────────────────────────────────────────

.PHONY: divergence
divergence: divergence-tables divergence-figures
