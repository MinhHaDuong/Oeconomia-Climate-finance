# divergence.mk — Multi-channel structural break detection pipeline
#
# Include from the main Makefile:  include divergence.mk
#
# Architecture: one CSV per method via scripts/compute_divergence.py --method X
#
# Targets:
#   divergence-semantic  Compute semantic methods (S1-S4, C2ST_embedding)
#   divergence-lexical   Compute lexical methods (L1-L3, C2ST_lexical)
#   divergence-citation  Compute citation methods (G1-G8)
#   divergence-tables    All divergence CSVs
#   divergence-figures   Plot one figure per method
#   divergence           Both tables and figures
#   bootstrap-tables     R=200 bootstrap replicates for CI estimation (S2, L1, G9, G2)
#   subsample-tables     R=20 equal-n subsampling replicates for Z-ribbon (S2, L1, G9, G2)
#   divergence-summary   Join point estimates + bootstrap + null + ribbon per method
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
DIV_METHODS_C2ST_SEM := C2ST_embedding
DIV_METHODS_C2ST_LEX := C2ST_lexical
DIV_METHODS_CIT := G1_pagerank G2_spectral G3_coupling_age G4_cross_tradition \
                   G5_pref_attachment G6_entropy G7_disruption G8_betweenness \
                   G9_community

# ── Derived file lists ───────────────────────────────────────────────────

DIV_CSV_SEM := $(foreach m,$(DIV_METHODS_SEM),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_LEX := $(foreach m,$(DIV_METHODS_LEX),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_CIT := $(foreach m,$(DIV_METHODS_CIT),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_C2ST_SEM := $(foreach m,$(DIV_METHODS_C2ST_SEM),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_C2ST_LEX := $(foreach m,$(DIV_METHODS_C2ST_LEX),$(DIV_TABLES)/tab_div_$(m).csv)
DIV_CSV_C2ST := $(DIV_CSV_C2ST_SEM) $(DIV_CSV_C2ST_LEX)
DIV_CSV_ALL := $(DIV_CSV_SEM) $(DIV_CSV_LEX) $(DIV_CSV_CIT) $(DIV_CSV_C2ST)

# ── Semantic methods (depend on embeddings) ──────────────────────────────

$(foreach m,$(DIV_METHODS_SEM),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	$(UV_RUN) python $(DIV_DISPATCH) --method $(m) --output $$@))

# ── Lexical methods (depend on REFINED only) ─────────────────────────────

$(foreach m,$(DIV_METHODS_LEX),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_lexical.py $(REFINED) $(DIV_CFG) ; \
	$(UV_RUN) python $(DIV_DISPATCH) --method $(m) --output $$@))

# ── Citation methods (depend on REFINED + REFINED_CIT) ───────────────────

$(foreach m,$(DIV_METHODS_CIT),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_citation.py $(REFINED) $(REFINED_CIT) $(DIV_CFG) ; \
	$(UV_RUN) python $(DIV_DISPATCH) --method $(m) --output $$@))

# ── C2ST methods (embedding variant depends on embeddings, lexical on REFINED) ─

$(foreach m,$(DIV_METHODS_C2ST_SEM),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_c2st.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	$(UV_RUN) python $(DIV_DISPATCH) --method $(m) --output $$@))

$(foreach m,$(DIV_METHODS_C2ST_LEX),$(eval \
$(DIV_TABLES)/tab_div_$(m).csv: $(DIV_DISPATCH) scripts/_divergence_c2st.py $(REFINED) $(DIV_CFG) ; \
	$(UV_RUN) python $(DIV_DISPATCH) --method $(m) --output $$@))

# ── Convenience targets ──────────────────────────────────────────────────

.PHONY: divergence-semantic
divergence-semantic: $(DIV_CSV_SEM) $(DIV_CSV_C2ST_SEM)

.PHONY: divergence-lexical
divergence-lexical: $(DIV_CSV_LEX) $(DIV_CSV_C2ST_LEX)

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
	$(UV_RUN) python scripts/plot_divergence.py \
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
	$(UV_RUN) python $(SENS_SCRIPT) --method $(m) --projection pca --output $$@))

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_TABLES)/tab_sens_jl_$(m).csv: $(SENS_SCRIPT) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	$(UV_RUN) python $(SENS_SCRIPT) --method $(m) --projection jl --output $$@))

# Figures: one PNG per (method, projection) pair — 1 invocation = 1 figure
SENS_FIG_PCA := $(foreach m,$(SENS_METHODS),$(DIV_FIGS)/fig_sensitivity_pca_$(m).png)
SENS_FIG_JL  := $(foreach m,$(SENS_METHODS),$(DIV_FIGS)/fig_sensitivity_jl_$(m).png)
SENS_FIG_ALL := $(SENS_FIG_PCA) $(SENS_FIG_JL)

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_FIGS)/fig_sensitivity_pca_$(m).png: $(SENS_PLOT) $(DIV_TABLES)/tab_sens_pca_$(m).csv ; \
	$(UV_RUN) python $(SENS_PLOT) --palette gradient --input $(DIV_TABLES)/tab_sens_pca_$(m).csv --output $$@))

$(foreach m,$(SENS_METHODS),$(eval \
$(DIV_FIGS)/fig_sensitivity_jl_$(m).png: $(SENS_PLOT) $(DIV_TABLES)/tab_sens_jl_$(m).csv ; \
	$(UV_RUN) python $(SENS_PLOT) --aggregate ribbon --input $(DIV_TABLES)/tab_sens_jl_$(m).csv --output $$@))

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
	$(UV_RUN) python $(CP_SCRIPT) --output $@ --input $(DIV_CSV_ALL)

$(CV_TABLE): $(CV_SCRIPT) $(CP_TABLE)
	$(UV_RUN) python $(CV_SCRIPT) --output $@ --input $(CP_TABLE)

$(CP_FIG): $(CP_PLOT) $(CP_TABLE) $(CV_TABLE)
	$(UV_RUN) python $(CP_PLOT) --output $@ --input $(CP_TABLE) $(CV_TABLE)

.PHONY: changepoints-tables
changepoints-tables: $(CP_TABLE) $(CV_TABLE)

.PHONY: changepoints-figure
changepoints-figure: $(CP_FIG)

.PHONY: changepoints
changepoints: changepoints-tables changepoints-figure

# ── Null model (permutation Z-scores, ticket 0055) ─────────────────────
#
# For each method, permute before/after labels and recompute the statistic
# to build a null distribution.  Output: tab_null_{method}.csv
#
# NJOBS caps per-method joblib parallelism across (year, window) pairs.
# Default -1 uses all cores — fine for a single method, but oversubscribes
# when composed with `make -j`.  When running `make -jN null-model`, pass
# NJOBS ≈ cores/N  (e.g. on a 24-core box:  `make -j4 NJOBS=6 null-model`).
# GPU auto-detected for S2_energy / S1_MMD (precomputed distance matrix).
NJOBS ?= -1

NULL_DISPATCH := scripts/compute_null_model.py
NULL_METHODS_SEM := S2_energy
NULL_METHODS_LEX := L1
NULL_METHODS_LEX_L2L3 := L2 L3
NULL_METHODS_CIT := G9_community G2_spectral
NULL_METHODS := $(NULL_METHODS_SEM) $(NULL_METHODS_LEX) $(NULL_METHODS_LEX_L2L3) $(NULL_METHODS_CIT)
NULL_CSV := $(foreach m,$(NULL_METHODS),$(DIV_TABLES)/tab_null_$(m).csv)

# Semantic null models (depend on embeddings + divergence CSV)
$(foreach m,$(NULL_METHODS_SEM),$(eval \
$(DIV_TABLES)/tab_null_$(m).csv: $(NULL_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_semantic.py scripts/_permutation_accel.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	$(UV_RUN) python $(NULL_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --n-jobs $(NJOBS) --output $$@))

# Lexical null models — L1: JS divergence (depend on REFINED + divergence CSV)
$(foreach m,$(NULL_METHODS_LEX),$(eval \
$(DIV_TABLES)/tab_null_$(m).csv: $(NULL_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_lexical.py scripts/_permutation_accel.py $(REFINED) $(DIV_CFG) ; \
	$(UV_RUN) python $(NULL_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --n-jobs $(NJOBS) --output $$@))

# Lexical null models — L2/L3: use _permutation_lexical.py instead of _permutation_accel.py
$(foreach m,$(NULL_METHODS_LEX_L2L3),$(eval \
$(DIV_TABLES)/tab_null_$(m).csv: $(NULL_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_lexical.py scripts/_permutation_lexical.py $(REFINED) $(DIV_CFG) ; \
	$(UV_RUN) python $(NULL_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

# Citation null models (depend on REFINED + REFINED_CIT + divergence CSV)
$(foreach m,$(NULL_METHODS_CIT),$(eval \
$(DIV_TABLES)/tab_null_$(m).csv: $(NULL_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_citation.py scripts/_divergence_community.py scripts/_citation_methods.py $(REFINED) $(REFINED_CIT) $(DIV_CFG) ; \
	$(UV_RUN) python $(NULL_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --n-jobs $(NJOBS) --output $$@))

.PHONY: null-model
null-model: $(NULL_CSV)

# ── Bootstrap CIs (ticket 0047) ──────────────────────────────────────────
#
# NOT part of default divergence — run explicitly:
#   make bootstrap-tables
#   make divergence-summary
#
# For each method, resample with replacement K times and recompute
# the statistic.  Output: tab_boot_{method}.csv

BOOT_DISPATCH := scripts/compute_divergence_bootstrap.py
BOOT_METHODS_SEM := S2_energy
BOOT_METHODS_LEX := L1
BOOT_METHODS_CIT := G9_community G2_spectral
BOOT_METHODS := $(BOOT_METHODS_SEM) $(BOOT_METHODS_LEX) $(BOOT_METHODS_CIT)
BOOT_CSV := $(foreach m,$(BOOT_METHODS),$(DIV_TABLES)/tab_boot_$(m).csv)

# Semantic bootstrap (depends on embeddings + divergence CSV)
$(foreach m,$(BOOT_METHODS_SEM),$(eval \
$(DIV_TABLES)/tab_boot_$(m).csv: $(BOOT_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	$(UV_RUN) python $(BOOT_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

# Lexical bootstrap (depends on REFINED + divergence CSV)
$(foreach m,$(BOOT_METHODS_LEX),$(eval \
$(DIV_TABLES)/tab_boot_$(m).csv: $(BOOT_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_lexical.py $(REFINED) $(DIV_CFG) ; \
	$(UV_RUN) python $(BOOT_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

# Citation bootstrap (depends on REFINED + REFINED_CIT + divergence CSV)
$(foreach m,$(BOOT_METHODS_CIT),$(eval \
$(DIV_TABLES)/tab_boot_$(m).csv: $(BOOT_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_citation.py scripts/_divergence_community.py scripts/_citation_methods.py $(REFINED) $(REFINED_CIT) $(DIV_CFG) ; \
	$(UV_RUN) python $(BOOT_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

.PHONY: bootstrap-tables
bootstrap-tables: $(BOOT_CSV)

# ── Divergence subsampling ribbon (ticket 0084) ──────────────────────────
#
# Draws R equal-n subsamples per (year, window) cell to estimate variance.
# Supports semantic, lexical, and the two lead citation methods (G2, G9).
# Output: tab_subsample_{method}.csv

SUBSAMP_DISPATCH := scripts/compute_divergence_subsampled.py
SUBSAMP_METHODS_SEM := S2_energy
SUBSAMP_METHODS_LEX := L1
SUBSAMP_METHODS_CIT := G9_community G2_spectral
SUBSAMP_METHODS := $(SUBSAMP_METHODS_SEM) $(SUBSAMP_METHODS_LEX) $(SUBSAMP_METHODS_CIT)
SUBSAMP_CSV := $(foreach m,$(SUBSAMP_METHODS),$(DIV_TABLES)/tab_subsample_$(m).csv)

$(foreach m,$(SUBSAMP_METHODS_SEM),$(eval \
$(DIV_TABLES)/tab_subsample_$(m).csv: $(SUBSAMP_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG) ; \
	$(UV_RUN) python $(SUBSAMP_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

$(foreach m,$(SUBSAMP_METHODS_LEX),$(eval \
$(DIV_TABLES)/tab_subsample_$(m).csv: $(SUBSAMP_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_lexical.py $(REFINED) $(DIV_CFG) ; \
	$(UV_RUN) python $(SUBSAMP_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

$(foreach m,$(SUBSAMP_METHODS_CIT),$(eval \
$(DIV_TABLES)/tab_subsample_$(m).csv: $(SUBSAMP_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv scripts/_divergence_citation.py scripts/_divergence_community.py scripts/_citation_methods.py $(REFINED) $(REFINED_CIT) $(DIV_CFG) ; \
	$(UV_RUN) python $(SUBSAMP_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --output $$@))

.PHONY: subsample-tables
subsample-tables: $(SUBSAMP_CSV)

# ── Divergence summary (ticket 0047, ribbon ticket 0084) ─────────────────
#
# Joins point estimates + bootstrap CIs + null model into one table per method.
# For all four lead methods, also joins subsampling ribbon columns.

SUMM_DISPATCH := scripts/export_divergence_summary.py
SUMM_CSV := $(foreach m,$(BOOT_METHODS),$(DIV_TABLES)/tab_summary_$(m).csv)

# Summary with ribbon (all four lead methods — S2, L1, G9, G2)
$(foreach m,$(SUBSAMP_METHODS),$(eval \
$(DIV_TABLES)/tab_summary_$(m).csv: $(SUMM_DISPATCH) $(DIV_TABLES)/tab_div_$(m).csv $(DIV_TABLES)/tab_boot_$(m).csv $(DIV_TABLES)/tab_null_$(m).csv $(DIV_TABLES)/tab_subsample_$(m).csv ; \
	$(UV_RUN) python $(SUMM_DISPATCH) --method $(m) --div-csv $(DIV_TABLES)/tab_div_$(m).csv --boot-csv $(DIV_TABLES)/tab_boot_$(m).csv --null-csv $(DIV_TABLES)/tab_null_$(m).csv --subsample-csv $(DIV_TABLES)/tab_subsample_$(m).csv --output $$@))

.PHONY: divergence-summary
divergence-summary: $(SUMM_CSV)

# ── Top-level ────────────────────────────────────────────────────────────

.PHONY: divergence
divergence: divergence-tables divergence-figures changepoints
