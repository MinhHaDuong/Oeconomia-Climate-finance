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

$(ZOO_TABLES)/tab_crossyear_%.csv: $(ZOO_TABLES)/tab_div_%.csv scripts/compute_crossyear_zscore.py
	$(UV_RUN) python scripts/compute_crossyear_zscore.py --method $* --output $@

# ── Zoo result panel recipes (pattern rule) ───────────────────────────────
#
# One diagnostic figure per method showing Z(t,w) for w=2..5.
# Degrades gracefully: writes a placeholder figure if the CSV is absent.

$(ZOO_FIGS)/fig_zoo_%.png: $(ZOO_TABLES)/tab_crossyear_%.csv scripts/plot_zoo_results.py
	$(UV_RUN) python scripts/plot_zoo_results.py --method $* --output $@

# ── Zoo PDF render (Phase 3) ─────────────────────────────────────────────────
# Thin wrapper over $(ZOO_INCLUDES) for reviewers or cherry-picking.
# Mirrors the TR recipe; same vars file, same bibliography, same engine.
output/content/zoo-breakpoint-detection-methods.pdf: content/zoo-breakpoint-detection-methods.qmd $(PROJECT_INCLUDES) $(BIB) content/technical-report-vars.yml $(ZOO_FIGS)
	quarto render $< --to pdf
