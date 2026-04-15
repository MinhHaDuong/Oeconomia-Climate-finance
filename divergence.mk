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

# ── Embedding sensitivity (ticket 0036) ─────────────────────────────────
#
# PCA dimensionality sweep and Johnson-Lindenstrauss random projections.
# Tests whether structural breaks survive dimensionality reduction.

SENS_SCRIPT := scripts/compute_embedding_sensitivity.py
SENS_PLOT   := scripts/plot_divergence.py
SENS_METHODS := S1_MMD S2_energy

# Tables: one CSV per (method, projection) pair
SENS_CSV_PCA := $(foreach m,$(SENS_METHODS),$(DIV_TABLES)/tab_sens_pca_$(m).csv)
SENS_CSV_JL  := $(foreach m,$(SENS_METHODS),$(DIV_TABLES)/tab_sens_jl_$(m).csv)
SENS_CSV_ALL := $(SENS_CSV_PCA) $(SENS_CSV_JL)

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_TABLES)/tab_sens_pca_$(m).csv: $(SENS_SCRIPT) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	python3 $(SENS_SCRIPT) --method $(m) --projection pca --output $$@))

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_TABLES)/tab_sens_jl_$(m).csv: $(SENS_SCRIPT) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	python3 $(SENS_SCRIPT) --method $(m) --projection jl --output $$@))

# Figures: one PNG per (method, projection) pair — 1 invocation = 1 figure
SENS_FIG_PCA := $(foreach m,$(SENS_METHODS),$(DIV_FIGS)/fig_sensitivity_pca_$(m).png)
SENS_FIG_JL  := $(foreach m,$(SENS_METHODS),$(DIV_FIGS)/fig_sensitivity_jl_$(m).png)
SENS_FIG_ALL := $(SENS_FIG_PCA) $(SENS_FIG_JL)

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_FIGS)/fig_sensitivity_pca_$(m).png: $(SENS_PLOT) $(DIV_TABLES)/tab_sens_pca_$(m).csv ; \
	python3 $(SENS_PLOT) --style gradient --input $(DIV_TABLES)/tab_sens_pca_$(m).csv --output $$@))

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_FIGS)/fig_sensitivity_jl_$(m).png: $(SENS_PLOT) $(DIV_TABLES)/tab_sens_jl_$(m).csv ; \
	python3 $(SENS_PLOT) --style ribbon --input $(DIV_TABLES)/tab_sens_jl_$(m).csv --output $$@))

.PHONY: sensitivity-tables
sensitivity-tables: $(SENS_CSV_ALL)

.PHONY: sensitivity-figures
sensitivity-figures: $(SENS_FIG_ALL)

.PHONY: sensitivity
sensitivity: sensitivity-tables sensitivity-figures

# ── Changepoints (ticket 0032) ──────────────────────────────────────────
#
# 1 script = 1 table:
#   compute_changepoints.py → tab_changepoints.csv (breaks)
#   compute_convergence.py  → tab_convergence.csv  (cross-method agreement)
#   plot_convergence.py     → fig_convergence.png  (heatmap + bars)

CP_SCRIPT  := scripts/compute_changepoints.py
CV_SCRIPT  := scripts/compute_convergence.py
CP_PLOT    := scripts/plot_convergence.py
CP_TABLE   := $(DIV_TABLES)/tab_changepoints.csv
CV_TABLE   := $(DIV_TABLES)/tab_convergence.csv
CP_FIG     := $(DIV_FIGS)/fig_convergence.png

$(CP_TABLE): $(CP_SCRIPT) $(DIV_CSV_ALL) $(DIV_CFG)
	python3 $(CP_SCRIPT) --output $@ --input $(DIV_CSV_ALL)

$(CV_TABLE): $(CV_SCRIPT) $(CP_TABLE)
	python3 $(CV_SCRIPT) --output $@ --input $(CP_TABLE)

$(CP_FIG): $(CP_PLOT) $(CP_TABLE) $(CV_TABLE)
	python3 $(CP_PLOT) --output $@ --input $(CP_TABLE)

.PHONY: changepoints-tables
changepoints-tables: $(CP_TABLE) $(CV_TABLE)

.PHONY: changepoints-figure
changepoints-figure: $(CP_FIG)

.PHONY: changepoints
changepoints: changepoints-tables changepoints-figure

# ── Top-level ────────────────────────────────────────────────────────────

.PHONY: divergence
divergence: divergence-tables divergence-figures changepoints
