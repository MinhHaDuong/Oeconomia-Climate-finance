# zoo.mk — Zoo figures: 17 ELI15 schematics + 18 cross-year result panels
#
# Included from the main Makefile:  -include zoo.mk
#
# Targets:
#   zoo-figures      All 35 zoo figures (schematics + result panels)
#   crossyear-tables Cross-year Z-score CSVs (prerequisites for result panels)
#
# Schematic stems match the plot_schematic_*.py script suffixes exactly.
# Result method names match the CROSSYEAR_METHODS list (18 methods).

# ── Paths ─────────────────────────────────────────────────────────────────

ZOO_FIGS   := content/figures
ZOO_TABLES := content/tables

# ── Schematic stems (match plot_schematic_{stem}.py filenames) ────────────

ZOO_SCHEMATIC_STEMS := \
    S1_mmd S2_energy S3_sliced_wasserstein S4_frechet \
    L1_js L2_ntr L3_burst \
    G1_pagerank G2_spectral G3_coupling_age G4_cross_tradition \
    G5_pref_attachment G6_entropy G7_disruption G8_betweenness \
    G9_community C2ST

ZOO_SCHEMATICS := $(addprefix $(ZOO_FIGS)/schematic_,$(addsuffix .png,$(ZOO_SCHEMATIC_STEMS)))

# ── Cross-year result methods ─────────────────────────────────────────────
#
# These are the methods for which tab_crossyear_{method}.csv is produced by
# compute_crossyear_zscore.py (depends on tab_div_{method}.csv).

CROSSYEAR_METHODS := S1_MMD S2_energy S3_sliced_wasserstein S4_frechet \
                     L1 L2 L3 G1_pagerank G2_spectral G3_coupling_age \
                     G4_cross_tradition G5_pref_attachment G6_entropy \
                     G7_disruption G8_betweenness G9_community \
                     C2ST_embedding C2ST_lexical

ZOO_RESULT_FIGS := $(addprefix $(ZOO_FIGS)/fig_zoo_,$(addsuffix .png,$(CROSSYEAR_METHODS)))

# ── Top-level phony target ────────────────────────────────────────────────

.PHONY: zoo-figures
zoo-figures: $(ZOO_SCHEMATICS) $(ZOO_RESULT_FIGS)

# ── Schematic recipes (pattern rule) ─────────────────────────────────────
#
# Each script accepts --output <path>.  No corpus data needed — scripts load
# real embeddings when available and fall back to synthetic data otherwise.

$(ZOO_FIGS)/schematic_%.png: scripts/plot_schematic_%.py scripts/script_io_args.py
	$(UV_RUN) python $< --output $@

# ── Cross-year Z-score tables ─────────────────────────────────────────────
#
# Standardise D(t,w) across years to produce Z(t,w).
# Output: content/tables/tab_crossyear_{method}.csv
# Depends only on the corresponding tab_div_{method}.csv.

.PHONY: crossyear-tables
crossyear-tables: $(addprefix $(ZOO_TABLES)/tab_crossyear_,$(addsuffix .csv,$(CROSSYEAR_METHODS)))

# L2: filter to resonance-only before Z-scoring to align with run_l2_permutations (ticket 0112).
$(ZOO_TABLES)/tab_crossyear_L2.csv: $(ZOO_TABLES)/tab_div_L2.csv scripts/compute_crossyear_zscore.py
	$(UV_RUN) python scripts/compute_crossyear_zscore.py --method L2 --metric resonance --output $@

$(ZOO_TABLES)/tab_crossyear_%.csv: $(ZOO_TABLES)/tab_div_%.csv scripts/compute_crossyear_zscore.py
	$(UV_RUN) python scripts/compute_crossyear_zscore.py --method $* --output $@

# ── Zoo result panel recipes (pattern rule) ───────────────────────────────
#
# One diagnostic figure per method showing Z(t,w) for w=2..5.
# Degrades gracefully: writes a placeholder figure if the CSV is absent.
#
# Methods with null model tables get an explicit target that passes --null-ci
# so the CI band overlay is rendered.  The pattern rule handles all others.

# Methods with null model tables: extra dep so figures rebuild when null data changes.
NULL_METHODS_ALL := S1_MMD S2_energy S3_sliced_wasserstein S4_frechet \
                    L1 L2 L3 \
                    G1_pagerank G2_spectral G5_pref_attachment G6_entropy \
                    G8_betweenness G9_community \
                    C2ST_embedding C2ST_lexical
$(foreach m,$(NULL_METHODS_ALL),$(eval \
  $(ZOO_FIGS)/fig_zoo_$(m).png: $(ZOO_TABLES)/tab_null_$(m).csv))

# Pattern rule for all methods: passes --null-ci when tab_null_*.csv exists.
$(ZOO_FIGS)/fig_zoo_%.png: $(ZOO_TABLES)/tab_crossyear_%.csv scripts/plot_zoo_results.py
	$(UV_RUN) python scripts/plot_zoo_results.py --method $* --output $@ \
		$(if $(wildcard $(ZOO_TABLES)/tab_null_$*.csv),--null-ci $(ZOO_TABLES)/tab_null_$*.csv,)

# ── Bias comparison tables (equal_n=false) ───────────────────────────────────
#
# Four representative methods: two semantic, one lexical, one C2ST.
# Each recipe mirrors the corresponding debiased recipe but adds --no-equal-n.

BIAS_METHODS := S1_MMD S2_energy L1 C2ST_embedding

$(ZOO_TABLES)/tab_div_biased_S1_MMD.csv: $(DIV_DISPATCH) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG)
	$(UV_RUN) python $(DIV_DISPATCH) --method S1_MMD --no-equal-n --output $@

$(ZOO_TABLES)/tab_div_biased_S2_energy.csv: $(DIV_DISPATCH) scripts/_divergence_semantic.py $(REFINED) $(REFINED_EMB) $(DIV_CFG)
	$(UV_RUN) python $(DIV_DISPATCH) --method S2_energy --no-equal-n --output $@

$(ZOO_TABLES)/tab_div_biased_L1.csv: $(DIV_DISPATCH) scripts/_divergence_lexical.py $(REFINED) $(DIV_CFG)
	$(UV_RUN) python $(DIV_DISPATCH) --method L1 --no-equal-n --output $@

$(ZOO_TABLES)/tab_div_biased_C2ST_embedding.csv: $(DIV_DISPATCH) scripts/_divergence_c2st.py $(REFINED) $(REFINED_EMB) $(DIV_CFG)
	$(UV_RUN) python $(DIV_DISPATCH) --method C2ST_embedding --no-equal-n --output $@

BIAS_FIGS := $(foreach m,$(BIAS_METHODS),$(ZOO_FIGS)/fig_zoo_bias_$(m).png)

$(ZOO_FIGS)/fig_zoo_bias_%.png: scripts/plot_zoo_bias_comparison.py \
    $(ZOO_TABLES)/tab_div_%.csv $(ZOO_TABLES)/tab_div_biased_%.csv
	$(UV_RUN) python scripts/plot_zoo_bias_comparison.py --method $* \
	    --input $(ZOO_TABLES)/tab_div_$*.csv \
	    --biased-csv $(ZOO_TABLES)/tab_div_biased_$*.csv \
	    --output $@

.PHONY: bias-tables bias-figures
bias-tables: $(foreach m,$(BIAS_METHODS),$(ZOO_TABLES)/tab_div_biased_$(m).csv)
bias-figures: $(BIAS_FIGS)

# ── Zoo PDF render (Phase 3) ─────────────────────────────────────────────────
# Thin wrapper over $(ZOO_INCLUDES) for reviewers or cherry-picking.
# Mirrors the TR recipe; same vars file, same bibliography, same engine.
output/content/breakpoint-detect-method-zoo.pdf: content/breakpoint-detect-method-zoo.qmd $(PROJECT_INCLUDES) $(BIB) content/technical-report-vars.yml $(ZOO_FIGS)
	quarto render $< --to pdf
