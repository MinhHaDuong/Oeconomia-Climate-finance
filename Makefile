# Makefile — Counting Climate Finance (Œconomia)
#
# Four-phase pipeline, namespaced by concern:
#   corpus-*      Phase 1: collection, enrichment, alignment (slow, API-dependent)
#   analysis-*    Phase 2: embeddings, clustering, figures (fast, deterministic)
#   manuscript-*  Phase 3: Oeconomia article rendering
#   datapaper-*   Phase 3: RDJ4HSS data paper rendering
#   archive-*     Phase 4: release & reproducibility packages
#
# Usage:
#   make                    Build manuscript (default)
#   make manuscript         Build manuscript only (PDF + DOCX)
#   make papers             Build all documents
#   make analysis-figures   Regenerate all figures
#   make analysis-stats     Recompute computed variables
#   make corpus             Full Phase 1 pipeline (padme only)
#   make corpus-handoff     Convert CSV→Feather for faster Phase 2 reads (optional)
#   make corpus-sync        Pull data from padme (doudou only)
#   make archive-manuscript Minimal package for Oeconomia reviewers
#   make archive-datapaper  Full pipeline package for data paper
#   make clean              Remove build outputs
#   make rebuild            Clean + rebuild everything

# ── Paths ─────────────────────────────────────────────────
# Data lives in data/catalogs/ (managed by DVC).
# Python scripts resolve the same path via utils.py (BASE_DIR/data).
DATA_DIR     := data/catalogs
CONFIG       := config/analysis.yaml
BIB         := content/bibliography/main.bib
CSL         := content/bibliography/oeconomia.csl
SRC         := content/manuscript.qmd

# Phase 1 artifact chain (the contract between phases)
UNIFIED     := $(DATA_DIR)/unified_works.csv
ENRICHED    := $(DATA_DIR)/enriched_works.csv
EXTENDED    := $(DATA_DIR)/extended_works.csv
REFINED     := $(DATA_DIR)/refined_works.csv
REFINED_EMB := $(DATA_DIR)/refined_embeddings.npz
REFINED_CIT := $(DATA_DIR)/refined_citations.csv
MOSTCITED   := $(DATA_DIR)/het_mostcited_50.csv

# Phase 1→2 handoff: Feather files for fast Phase 2 reads
REFINED_FTH := $(DATA_DIR)/refined_works.feather
REFINED_CIT_FTH := $(DATA_DIR)/refined_citations.feather

# ── Reproducibility ───────────────────────────────────────
# PYTHONHASHSEED=0  → deterministic dict/set iteration order
# SOURCE_DATE_EPOCH=0 → reproducible timestamps in PDF/PNG metadata
export PYTHONHASHSEED := 0
export SOURCE_DATE_EPOCH := 0

# ── Toolchain ─────────────────────────────────────────────
# Named tool variables so invocations stay overridable and self-documenting.
# PATH export covers non-interactive shells (ssh, cron, systemd) where
# ~/.bashrc isn't sourced — uv lives in ~/.local/bin by default.
UV      ?= uv
UV_RUN  ?= $(UV) run
export PATH := $(HOME)/.local/bin:$(PATH)

# ── Modular Makefile includes ────────────────────────────
-include divergence.mk
-include companion.mk
-include zoo.mk

# ── Quarto ───────────────────────────────────────────────
# ── Per-document include sets ────────────────────────────
MANUSCRIPT_INCLUDES := content/tables/tab_venues.md

TECHREP_INCLUDES := content/_includes/corpus-construction.md \
		content/_includes/corpus-enrichment.md \
		content/_includes/corpus-filtering.md \
		content/_includes/core-vs-full.md \
		content/_includes/structural-breaks.md \
		content/_includes/alluvial-diagram.md \
		content/_includes/bimodality-analysis.md \
		content/_includes/pca-scatter.md \
		content/_includes/citation-genealogy.md \
		content/_includes/cocitation-communities.md \
		content/_includes/citation-quality.md \
		content/_includes/reproducibility.md \
		content/tables/tab_citation_coverage.md

DATAPAPER_INCLUDES := content/_includes/corpus-construction.md \
		content/_includes/corpus-filtering.md \
		content/_includes/embedding-generation.md \
		content/_includes/reproducibility.md \
		content/tables/tab_corpus_sources.md \
		content/tables/tab_languages.md

COMPANION_INCLUDES := content/_includes/embedding-generation.md \
		content/_includes/structural-breaks.md \
		content/_includes/alluvial-diagram.md \
		content/_includes/bimodality-analysis.md \
		content/_includes/pca-scatter.md \
		content/_includes/core-vs-full.md

# Method-zoo include tree: one composer + 18 per-method entries.
# Used by the zoo-only wrapper and transitively by technical-report.qmd.
ZOO_INCLUDES := content/_includes/techrep/overview.md \
		content/_includes/techrep/zscore.md \
		content/_includes/techrep/null-model.md \
		content/_includes/techrep-zoo.md \
		content/_includes/zoo/S1_mmd.md \
		content/_includes/zoo/S2_energy.md \
		content/_includes/zoo/S3_sliced_wasserstein.md \
		content/_includes/zoo/S4_frechet.md \
		content/_includes/zoo/C2ST_embedding.md \
		content/_includes/zoo/L1_js.md \
		content/_includes/zoo/L2_ntr.md \
		content/_includes/zoo/L3_term_burst.md \
		content/_includes/zoo/C2ST_lexical.md \
		content/_includes/zoo/G1_pagerank.md \
		content/_includes/zoo/G2_spectral.md \
		content/_includes/zoo/G3_coupling_age.md \
		content/_includes/zoo/G4_cross_tradition.md \
		content/_includes/zoo/G5_pref_attachment.md \
		content/_includes/zoo/G6_entropy.md \
		content/_includes/zoo/G7_disruption.md \
		content/_includes/zoo/G8_betweenness.md \
		content/_includes/zoo/G9_community.md

# Quarto resolves includes across ALL project files (_quarto.yml render list),
# even when rendering a single document. Every render target needs the full set.
PROJECT_INCLUDES := $(MANUSCRIPT_INCLUDES) $(TECHREP_INCLUDES) \
		$(DATAPAPER_INCLUDES) $(COMPANION_INCLUDES) $(ZOO_INCLUDES)

# ── Per-document figure sets ─────────────────────────────
MANUSCRIPT_FIGS := content/figures/fig_bars_v1.png content/figures/fig_composition.png

DATAPAPER_FIGS  := content/figures/fig_bars.png content/figures/fig_dag.png

COMPANION_FIGS  := content/figures/fig_breakpoints.png content/figures/fig_alluvial.png \
                   content/figures/fig_breaks.png \
                   content/figures/fig_bimodality.png \
                   content/figures/fig_seed_axis_core.png content/figures/fig_pca_scatter.png \
                   content/figures/fig_genealogy.png \
                   content/figures/fig_companion_zseries.png \
                   content/figures/fig_companion_heatmap.png \
                   content/figures/fig_companion_terms.png \
                   content/figures/fig_companion_community.png

TECHREP_FIGS    := content/figures/fig_alluvial_core.png \
                   content/figures/fig_bimodality_core.png \
                   content/figures/fig_bimodality_lexical_core.png \
                   content/figures/fig_bimodality_keywords_core.png \
                   content/figures/fig_bimodality_lexical.png \
                   content/figures/fig_bimodality_keywords.png \
                   content/figures/fig_kde.png \
                   content/figures/fig_traditions.png \
                   content/figures/fig_communities.png \
                   content/figures/fig_semantic.png \
                   content/figures/fig_semantic_lang.png \
                   content/figures/fig_semantic_period.png

NCC_FIGS        := content/figures/fig_ncc_divergence.png \
                   content/figures/fig_ncc_core_comparison.png \
                   content/figures/fig_ncc_bimodality.png \
                   content/figures/fig_ncc_alluvial.png

# Method-zoo figures (17 schematics + 18 zoo result panels).
# schematic_C2ST.png serves both C2ST_embedding and C2ST_lexical, hence 17 schematics for 18 methods.
ZOO_SCHEMATICS := content/figures/schematic_S1_mmd.png \
                  content/figures/schematic_S2_energy.png \
                  content/figures/schematic_S3_sliced_wasserstein.png \
                  content/figures/schematic_S4_frechet.png \
                  content/figures/schematic_C2ST.png \
                  content/figures/schematic_L1_js.png \
                  content/figures/schematic_L2_ntr.png \
                  content/figures/schematic_L3_burst.png \
                  content/figures/schematic_G1_pagerank.png \
                  content/figures/schematic_G2_spectral.png \
                  content/figures/schematic_G3_coupling_age.png \
                  content/figures/schematic_G4_cross_tradition.png \
                  content/figures/schematic_G5_pref_attachment.png \
                  content/figures/schematic_G6_entropy.png \
                  content/figures/schematic_G7_disruption.png \
                  content/figures/schematic_G8_betweenness.png \
                  content/figures/schematic_G9_community.png

ZOO_RESULT_FIGS := content/figures/fig_zoo_S1_MMD.png \
                   content/figures/fig_zoo_S2_energy.png \
                   content/figures/fig_zoo_S3_sliced_wasserstein.png \
                   content/figures/fig_zoo_S4_frechet.png \
                   content/figures/fig_zoo_C2ST_embedding.png \
                   content/figures/fig_zoo_C2ST_lexical.png \
                   content/figures/fig_zoo_L1.png \
                   content/figures/fig_zoo_L2.png \
                   content/figures/fig_zoo_L3.png \
                   content/figures/fig_zoo_G1_pagerank.png \
                   content/figures/fig_zoo_G2_spectral.png \
                   content/figures/fig_zoo_G3_coupling_age.png \
                   content/figures/fig_zoo_G4_cross_tradition.png \
                   content/figures/fig_zoo_G5_pref_attachment.png \
                   content/figures/fig_zoo_G6_entropy.png \
                   content/figures/fig_zoo_G7_disruption.png \
                   content/figures/fig_zoo_G8_betweenness.png \
                   content/figures/fig_zoo_G9_community.png

ZOO_FIGS := $(ZOO_SCHEMATICS) $(ZOO_RESULT_FIGS)

# ZOO_FIGS deliberately excluded from ALL_FIGS / make figures: plot scripts not yet wired.
# Add to ALL_FIGS when plot_schematic_*.py and plot_zoo_results.py have Makefile targets.
ALL_FIGS := $(MANUSCRIPT_FIGS) $(DATAPAPER_FIGS) $(COMPANION_FIGS) $(TECHREP_FIGS) $(NCC_FIGS)

# ── Default target ────────────────────────────────────────
.PHONY: all setup manuscript papers figures figures-manuscript figures-datapaper figures-companion figures-techrep figures-ncc stats check check-fast smoke benchmark determinism-check regression regression-update check-corpus check-manuscript-data corpus corpus-sync corpus-discover corpus-enrich corpus-extend corpus-filter corpus-align corpus-filter-all corpus-tables corpus-validate deploy-corpus clean rebuild archive-analysis archive-manuscript archive-datapaper analysis-figures analysis-tables analysis-stats manuscript-render manuscript-figures datapaper-render datapaper-figures corpus-handoff

.DEFAULT_GOAL := manuscript

all: manuscript papers

# ═══════════════════════════════════════════════════════════
# PHASE 1 — Corpus Building (slow, API-dependent, run rarely)
# ═══════════════════════════════════════════════════════════
#
# Artifact chain (the contract between sub-phases):
#   1a unified_works.csv      raw merged catalog, no filtering
#   1b enriched_works.csv     metadata/abstract/DOI enrichment applied
#      + citations.csv        full citation graph (cache)
#      + embeddings.npz       sentence embeddings (cache)
#   1c extended_works.csv     diagnostic flags/protection columns added, no rows removed
#   1d refined_works.csv      keep/remove policy applied; corpus_audit.csv produced
#   1e refined_embeddings.npz embedding vectors aligned 1:1 with refined_works.csv rows
#      refined_citations.csv  citation edges restricted to refined DOIs (Phase 2 canonical)
#
# Phase 2 scripts read ONLY: refined_works.csv, refined_embeddings.npz, refined_citations.csv.
# (embeddings.npz and citations.csv are enrichment caches, not Phase 2 inputs.)
# het_mostcited_50.csv is a Phase 2 derived product (build_het_core.py).

# ── DVC workflow ─────────────────────────────────────────
#
# Phase 1 data is managed by DVC (see dvc.yaml for the pipeline DAG).
# DVC tracks file hashes: it skips stages whose inputs are unchanged.
#
# Padme is the data authority. Run the pipeline on padme, pull on doudou.
#
# On padme (pipeline run):
#   make corpus                      # dvc repro + push + commit lock
#
# On doudou (sync only):
#   make corpus-sync                 # git pull + dvc pull
#   make figures && make manuscript  # Phase 2 + 3 (no DVC needed)

# Full pipeline — run on padme only (GPU, API access).
# After dvc repro + push, auto-commits dvc.lock if it's the only change.
corpus:
	bash scripts/run_corpus_pipeline.sh

# Sync data from padme — run on doudou (never pushes).
corpus-sync:
	@[ "$$(hostname)" != "padme" ] || { echo "error: use 'make corpus' on padme, not corpus-sync."; exit 1; }
	git pull
	$(UV_RUN) dvc pull --force

# Individual stage aliases.
corpus-discover:
	$(UV_RUN) dvc repro catalog_merge

corpus-enrich:
	$(UV_RUN) dvc repro enrich_dois enrich_abstracts enrich_language summarize_abstracts join_enrichments enrich_citations qa_citations enrich_embeddings

corpus-extend:
	$(UV_RUN) dvc repro extend

corpus-filter:
	$(UV_RUN) dvc repro filter

corpus-filter-all:
	$(UV_RUN) dvc repro extend filter

corpus-align:
	$(UV_RUN) dvc repro align

# Upload artifacts to the DVC remote (padme).
deploy-corpus:
	$(UV_RUN) dvc push

# ── Corpus diagnostics (Phase 1 — reads enrichment caches) ──
content/tables/qa_citations_report.json: scripts/qa_citations.py scripts/utils.py \
		$(DATA_DIR)/citations.csv
	$(UV_RUN) python $<

# ═══════════════════════════════════════════════════════════
# PHASE 2 — Analysis & Figures (fast, deterministic, run often)
# ═══════════════════════════════════════════════════════════
# Inputs: Phase 1 outputs only (refined_works.csv, refined_embeddings.npz, refined_citations.csv).
# het_mostcited_50.csv is produced within Phase 2 by build_het_core.py.
# Outputs: content/figures/*.png, content/tables/*.csv, content/*-vars.yml

# Gate for Phase 2: verify all three contract files exist.
# If any is missing, suggest dvc pull (data not synced) or make corpus (not built).
# Phase 1→2 handoff: convert CSV contract files to Feather for fast Phase 2 reads.
# Embeddings stay as .npz (already binary). One conversion pass (~5s) replaces
# ~48s of repeated CSV parsing across 25 Phase 2 script invocations.
$(REFINED_FTH): $(REFINED)
	$(UV_RUN) python -c "import pandas as pd; pd.read_csv('$<').to_feather('$@')"

$(REFINED_CIT_FTH): $(REFINED_CIT)
	$(UV_RUN) python -c "import pandas as pd; pd.read_csv('$<', low_memory=False).to_feather('$@')"

corpus-handoff: check-corpus $(REFINED_FTH) $(REFINED_CIT_FTH)

check-corpus:
	@ok=true; \
	for f in "$(REFINED)" "$(REFINED_EMB)" "$(REFINED_CIT)"; do \
		test -f "$$f" || { echo "MISSING: $$f"; ok=false; }; \
	done; \
	$$ok || { echo "Run '$(UV_RUN) dvc pull' to sync data, or 'make corpus' to rebuild."; exit 1; }

# Lighter gate for manuscript-only builds (no citations needed).
check-manuscript-data:
	@ok=true; \
	for f in "$(REFINED)" "$(REFINED_EMB)"; do \
		test -f "$$f" || { echo "MISSING: $$f"; ok=false; }; \
	done; \
	$$ok || { echo "Run '$(UV_RUN) dvc pull' to sync data, or 'make corpus' to rebuild."; exit 1; }

corpus-validate: $(REFINED)
	$(UV_RUN) pytest tests/test_corpus_acceptance.py -v -s --tb=long

# ── Corpus reporting (Phase 2 — reads only refined data) ──
content/tables/tab_citation_coverage.md: scripts/export_citation_coverage.py scripts/utils.py $(REFINED)
	$(UV_RUN) python $< --output $@

content/tables/tab_venues.md: scripts/export_tab_venues.py scripts/utils.py $(REFINED) content/tables/tab_pole_papers.csv
	$(UV_RUN) python $< --output $@

content/tables/tab_corpus_sources.csv content/tables/tab_corpus_sources.md &: scripts/export_corpus_table.py scripts/utils.py $(REFINED)
	$(UV_RUN) python $< --output $@

content/tables/tab_languages.md: scripts/export_language_table.py scripts/utils.py $(ENRICHED)
	$(UV_RUN) python $< --output $@

corpus-tables: content/tables/tab_corpus_sources.csv content/tables/tab_corpus_sources.md \
               content/tables/tab_citation_coverage.md \
               content/tables/tab_languages.md

# ── Statistics (computed from pipeline outputs) ──────────
# manuscript-vars.yml is pinned to v1.0 values — not auto-generated by compute_vars.py.
COMPUTED_STATS := content/technical-report-vars.yml \
                  content/data-paper-vars.yml content/companion-paper-vars.yml

# Grouped target (&:) — one invocation writes all 3 files. Requires GNU Make >= 4.3.
$(COMPUTED_STATS) &: scripts/compute_vars.py scripts/utils.py $(REFINED) \
		content/tables/tab_bimodality.csv content/tables/tab_bimodality_core.csv \
		content/tables/tab_axis_detection.csv \
		$(wildcard $(UNIFIED)) \
		$(wildcard $(DATA_DIR)/corpus_audit.csv) \
		$(wildcard $(DATA_DIR)/embeddings.npz) \
		$(wildcard $(REFINED_EMB)) \
		$(wildcard $(DATA_DIR)/citations.csv) \
		$(wildcard $(REFINED_CIT)) \
		$(wildcard content/tables/qa_citations_report.json)
	$(UV_RUN) python $< --output $@

stats: $(COMPUTED_STATS)

# ── Tables (generated, included by Quarto) ──────────────

# Core subset → venues table
$(MOSTCITED): scripts/build_het_core.py scripts/utils.py $(REFINED) $(REFINED_CIT)
	$(UV_RUN) python $< --output $@

content/tables/tab_core_venues_top10.md: scripts/export_core_venues_markdown.py scripts/summarize_core_venues.py scripts/utils.py $(MOSTCITED)
	$(UV_RUN) python $< --output $@

# ── Figures ──────────────────────────────────────────────

# -- Manuscript (Oeconomia article) --
# Fig 1 (bars): corpus growth per year
content/figures/fig_bars.png: scripts/plot_fig1_bars.py scripts/plot_style.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@

# Fig 1 v1 variant: restricted to submission corpus for manuscript stability
content/figures/fig_bars_v1.png: scripts/plot_fig1_bars.py scripts/plot_style.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --v1-only

# Fig 2 (composition): frozen v1 archive data + corrected labels
content/figures/fig_composition.png: scripts/plot_fig2_composition.py scripts/plot_style.py scripts/utils.py $(CONFIG) \
		config/v1_tab_alluvial.csv config/v1_cluster_labels.json
	$(UV_RUN) python $< --output $@ --input config/v1_tab_alluvial.csv --labels config/v1_cluster_labels.json

# -- Data paper --
# Semantic clusters (computation only — no figures)
SEMANTIC_CLUSTERS := $(DATA_DIR)/semantic_clusters.csv

$(SEMANTIC_CLUSTERS): scripts/analyze_embeddings.py scripts/utils.py $(CONFIG) $(ENRICHED) $(DATA_DIR)/embeddings.npz
	$(UV_RUN) python $< --output $@

# Semantic UMAP maps (one parameterized plot script, 3 invocations)
content/figures/fig_semantic.png: scripts/plot_semantic.py scripts/utils.py $(SEMANTIC_CLUSTERS)
	$(UV_RUN) python $< --color-by cluster --output $@

content/figures/fig_semantic_lang.png: scripts/plot_semantic.py scripts/utils.py $(SEMANTIC_CLUSTERS)
	$(UV_RUN) python $< --color-by language --output $@

content/figures/fig_semantic_period.png: scripts/plot_semantic.py scripts/utils.py $(SEMANTIC_CLUSTERS)
	$(UV_RUN) python $< --color-by period --output $@

# -- Companion paper (quantitative) --
# Structural break tables (independent of clustering)
content/tables/tab_breakpoints.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@

content/tables/tab_breakpoint_robustness.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --robustness

# Clustering + alluvial flow tables — full corpus (companion paper, tech report)
content/tables/tab_alluvial.csv content/tables/cluster_labels.json \
content/tables/tab_core_shares.csv &: \
		scripts/compute_clusters.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output content/tables/tab_alluvial.csv

# Clustering — v1 frozen from reproducibility archive (not re-clustered).
# KMeans is unstable to small corpus perturbations; re-clustering the v1
# subset produces different assignments. These checked-in files are the
# source of truth for manuscript Figure 2.
# To update: copy from the reproducibility archive and commit.

# Breakpoints figure
content/figures/fig_breakpoints.png: \
		scripts/plot_fig_breakpoints.py scripts/utils.py $(CONFIG) \
		content/tables/tab_breakpoints.csv content/tables/tab_breakpoint_robustness.csv \
		content/tables/tab_alluvial.csv
	$(UV_RUN) python $< --output $@ --input content/tables/tab_breakpoints.csv content/tables/tab_breakpoint_robustness.csv content/tables/tab_alluvial.csv

# Alluvial figure (static PNG)
content/figures/fig_alluvial.png: \
		scripts/plot_fig_alluvial.py scripts/utils.py $(CONFIG) \
		content/tables/tab_alluvial.csv content/tables/cluster_labels.json
	$(UV_RUN) python $< --output $@ --input content/tables/tab_alluvial.csv

# Alluvial figure (interactive HTML)
content/figures/fig_alluvial.html: \
		scripts/plot_alluvial_html.py scripts/utils.py $(CONFIG) \
		content/tables/tab_alluvial.csv content/tables/cluster_labels.json
	$(UV_RUN) python $< --output $@

# Period divergence curves
content/figures/fig_breaks.png: scripts/plot_fig2_breaks.py scripts/plot_style.py scripts/utils.py $(CONFIG) \
		content/tables/tab_breakpoints.csv
	$(UV_RUN) python $< --output $@ --input content/tables/tab_breakpoints.csv

# Bimodality tables (computation only — figures are separate targets below)
content/tables/tab_bimodality.csv content/tables/tab_axis_detection.csv \
content/tables/tab_pole_papers.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output content/tables/tab_bimodality.csv

# Bimodality figures (each reads tab_pole_papers.csv)
content/figures/fig_bimodality.png: scripts/plot_bimodality.py scripts/utils.py \
		content/tables/tab_pole_papers.csv
	$(UV_RUN) python $< --output $@

content/figures/fig_bimodality_lexical.png: scripts/plot_bimodality_lexical.py scripts/utils.py \
		content/tables/tab_pole_papers.csv
	$(UV_RUN) python $< --output $@

content/figures/fig_bimodality_keywords.png: scripts/plot_bimodality_keywords.py scripts/utils.py \
		content/tables/tab_pole_papers.csv
	$(UV_RUN) python $< --output $@

# Seed-axis violin (core, manuscript figure)
content/figures/fig_seed_axis_core.png: scripts/plot_fig_seed_axis.py scripts/plot_style.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@

# PCA scatter (unsupervised)
content/figures/fig_pca_scatter.png: scripts/plot_fig45_pca_scatter.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@

# Citation genealogy: model (lineage table) then renderers
content/tables/tab_lineages.csv: scripts/analyze_genealogy.py scripts/utils.py $(CONFIG) \
		$(REFINED) $(REFINED_CIT) content/tables/tab_pole_papers.csv $(SEMANTIC_CLUSTERS)
	$(UV_RUN) python $< --output $@

content/figures/fig_genealogy.png: scripts/plot_genealogy.py scripts/utils.py $(CONFIG) \
		content/tables/tab_lineages.csv $(REFINED_CIT)
	$(UV_RUN) python $< --output $@

content/figures/fig_genealogy.html: scripts/plot_genealogy_html.py scripts/utils.py $(CONFIG) \
		content/tables/tab_lineages.csv $(REFINED_CIT)
	$(UV_RUN) python $< --output $@

# -- Technical report (robustness, variants, supplementary) --
# Core-only: structural break tables
content/tables/tab_breakpoints_core.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --core-only

content/tables/tab_breakpoint_robustness_core.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --robustness --core-only

# Core-only: clustering + alluvial flow tables
content/tables/tab_alluvial_core.csv content/tables/cluster_labels_core.json &: \
		scripts/compute_clusters.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output content/tables/tab_alluvial_core.csv --core-only

# Core-only figures
content/figures/fig_breakpoints_core.png: \
		scripts/plot_fig_breakpoints.py scripts/utils.py $(CONFIG) \
		content/tables/tab_breakpoints_core.csv content/tables/tab_breakpoint_robustness_core.csv \
		content/tables/tab_alluvial_core.csv
	$(UV_RUN) python $< --output $@ --core-only --input content/tables/tab_breakpoints_core.csv content/tables/tab_breakpoint_robustness_core.csv content/tables/tab_alluvial_core.csv

content/figures/fig_alluvial_core.png: \
		scripts/plot_fig_alluvial.py scripts/utils.py $(CONFIG) \
		content/tables/tab_alluvial_core.csv content/tables/cluster_labels_core.json
	$(UV_RUN) python $< --output $@ --core-only --input content/tables/tab_alluvial_core.csv

# Bimodality core variant tables
content/tables/tab_bimodality_core.csv content/tables/tab_axis_detection_core.csv \
content/tables/tab_pole_papers_core.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output content/tables/tab_bimodality_core.csv --core-only

# Bimodality core variant figures
content/figures/fig_bimodality_core.png: scripts/plot_bimodality.py scripts/utils.py \
		content/tables/tab_pole_papers_core.csv
	$(UV_RUN) python $< --core-only --output $@

content/figures/fig_bimodality_lexical_core.png: scripts/plot_bimodality_lexical.py scripts/utils.py \
		content/tables/tab_pole_papers_core.csv
	$(UV_RUN) python $< --core-only --output $@

content/figures/fig_bimodality_keywords_core.png: scripts/plot_bimodality_keywords.py scripts/utils.py \
		content/tables/tab_pole_papers_core.csv
	$(UV_RUN) python $< --core-only --output $@

# Pre-2007 co-citation traditions network
content/figures/fig_traditions.png: scripts/plot_fig_traditions.py scripts/plot_style.py scripts/utils.py $(CONFIG) $(REFINED) $(REFINED_CIT)
	$(UV_RUN) python $< --output $@

# Co-citation communities (compute: community assignments + summary table)
COMMUNITIES := data/catalogs/communities.csv
$(COMMUNITIES): scripts/analyze_cocitation.py scripts/utils.py $(REFINED_CIT)
	$(UV_RUN) python $< --output $@

# Co-citation communities (plot: network figure)
content/figures/fig_communities.png: scripts/plot_cocitation.py scripts/utils.py $(COMMUNITIES) $(REFINED_CIT)
	$(UV_RUN) python $< --output $@ --input $(COMMUNITIES)

# KDE supplementary
content/figures/fig_kde.png: scripts/plot_figS_kde.py scripts/plot_style.py scripts/utils.py $(CONFIG) \
		content/tables/tab_pole_papers.csv
	$(UV_RUN) python $< --output $@

# Lexical TF-IDF table (diagnostic, not in manuscript)
content/tables/tab_lexical_tfidf.csv: scripts/compute_lexical.py scripts/utils.py $(REFINED) \
		content/tables/tab_breakpoint_robustness.csv
	$(UV_RUN) python $< --output $@

# Multilingual epistemic structure (exploratory JSON report)
content/tables/multilingual_report.json: scripts/analyze_multilingual.py scripts/utils.py \
		scripts/build_het_core.py $(REFINED) $(REFINED_EMB) $(REFINED_CIT) $(SEMANTIC_CLUSTERS)
	$(UV_RUN) python $< --output $@

# K-sensitivity table
content/tables/tab_k_sensitivity.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --k-sensitivity

# K-sensitivity figure
content/figures/fig_k_sensitivity.png: scripts/plot_fig_k_sensitivity.py $(CONFIG) \
		content/tables/tab_k_sensitivity.csv
	$(UV_RUN) python $< --output $@

# Lexical TF-IDF figures (one per detected break year; output filenames are
# dynamic, so we use a sentinel file to track freshness).
.lexical_tfidf.stamp: scripts/plot_fig_lexical_tfidf.py scripts/plot_style.py $(CONFIG) \
		content/tables/tab_lexical_tfidf.csv
	$(UV_RUN) python $< --output $@

# DVC pipeline DAG (data paper)
content/figures/fig_dag.png: scripts/plot_fig_dag.py scripts/plot_style.py $(CONFIG) dvc.yaml
	$(UV_RUN) python $< --output $@

# -- NCC Analysis (Nature Climate Change) --

# Censor-gap k=2 breakpoint tables (intermediate for NCC figure a)
content/tables/tab_breakpoints_censor2.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --censor-gap 2

content/tables/tab_breakpoint_robustness_censor2.csv: scripts/compute_breakpoints.py scripts/utils.py $(CONFIG) $(REFINED)
	$(UV_RUN) python $< --output $@ --robustness --censor-gap 2

# NCC Figure (a): Divergence with 2009 peak (baseline vs censor-gap k=2)
content/figures/fig_ncc_divergence.png: \
		scripts/plot_ncc_divergence.py scripts/utils.py $(CONFIG) \
		content/tables/tab_breakpoints.csv \
		content/tables/tab_breakpoints_censor2.csv \
		content/tables/tab_breakpoint_robustness_censor2.csv
	$(UV_RUN) python $< --output $@ --input content/tables/tab_breakpoints.csv content/tables/tab_breakpoints_censor2.csv content/tables/tab_breakpoint_robustness_censor2.csv

# NCC Figure (b): Core vs full corpus comparison panel
content/figures/fig_ncc_core_comparison.png: \
		scripts/plot_ncc_core_comparison.py scripts/utils.py $(CONFIG) \
		content/tables/tab_breakpoints.csv content/tables/tab_breakpoint_robustness.csv \
		content/tables/tab_alluvial.csv \
		content/tables/tab_breakpoints_core.csv content/tables/tab_breakpoint_robustness_core.csv \
		content/tables/tab_alluvial_core.csv
	$(UV_RUN) python $< --output $@

# NCC Figure (c): Bimodality KDE with period decomposition
content/figures/fig_ncc_bimodality.png: \
		scripts/plot_ncc_bimodality.py scripts/utils.py $(CONFIG) \
		content/tables/tab_pole_papers.csv
	$(UV_RUN) python $< --output $@

# NCC Figure (d): Alluvial diagram (NCC format)
content/figures/fig_ncc_alluvial.png: \
		scripts/plot_ncc_alluvial.py scripts/utils.py $(CONFIG) \
		content/tables/tab_alluvial.csv content/tables/cluster_labels.json
	$(UV_RUN) python $< --output $@ --input content/tables/tab_alluvial.csv

figures-manuscript: corpus-handoff $(MANUSCRIPT_FIGS)
figures-datapaper:  corpus-handoff $(DATAPAPER_FIGS)
figures-companion:  corpus-handoff $(COMPANION_FIGS)
figures-techrep:    corpus-handoff $(TECHREP_FIGS)
figures-ncc:        corpus-handoff $(NCC_FIGS)
figures: corpus-handoff $(ALL_FIGS) corpus-tables

# ── Namespaced aliases (Phase 2) ────────────────────────
# Organized by concern for discoverability: make analysis-<tab>
analysis-figures: figures
analysis-tables: corpus-tables $(MOSTCITED)
analysis-stats: stats

# ═══════════════════════════════════════════════════════════
# PHASE 3 — Render (Quarto → PDF/DOCX)
# ═══════════════════════════════════════════════════════════

manuscript: output/content/manuscript.pdf output/content/manuscript.docx

papers: check-corpus output/content/corpus-report.pdf output/content/technical-report.pdf output/content/zoo-only.pdf output/content/data-paper.pdf output/content/companion-paper.pdf

# ── Namespaced aliases (Phase 3) ────────────────────────
manuscript-render: manuscript
manuscript-figures: figures-manuscript

datapaper-render: output/content/data-paper.pdf
datapaper-figures: figures-datapaper

output/content/manuscript.pdf: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to pdf

output/content/manuscript.docx: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to docx

output/content/corpus-report.pdf: content/corpus-report.qmd $(PROJECT_INCLUDES) $(BIB) content/technical-report-vars.yml
	quarto render $< --to pdf

output/content/technical-report.pdf: content/technical-report.qmd $(PROJECT_INCLUDES) $(BIB) content/technical-report-vars.yml $(TECHREP_FIGS) $(COMPANION_FIGS) .lexical_tfidf.stamp
	quarto render $< --to pdf

output/content/data-paper.pdf: content/data-paper.qmd $(PROJECT_INCLUDES) $(BIB) content/data-paper-vars.yml
	quarto render $< --to pdf

output/content/companion-paper.pdf: content/companion-paper.qmd $(PROJECT_INCLUDES) $(BIB) content/companion-paper-vars.yml
	quarto render $< --to pdf

# ── Phase 4a — analysis archive (packages Phase 2 outputs) ─
# Data + scripts: reviewers verify figures/tables are reproducible.
#   tar xzf archive.tar.gz && cd ... && uv sync && make
SHELL            := /bin/bash
ANALYSIS_OUTPUTS := content/figures/fig_bars_v1.png \
                    content/figures/fig_composition.png \
                    content/tables/tab_venues.md \
                    content/tables/tab_alluvial.csv \
                    content/tables/tab_core_shares.csv \
                    content/tables/tab_bimodality.csv \
                    content/tables/tab_axis_detection.csv \
                    content/tables/tab_pole_papers.csv \
                    content/tables/cluster_labels.json

archive-analysis: check-manuscript-data $(ANALYSIS_OUTPUTS)
	bash release/scripts/build_analysis_archive.sh

# ── Phase 4b — manuscript archive (packages Phase 3 outputs) ─
# Pre-built figures + content: reviewers verify PDF renders.
# No Python needed — only Quarto + XeLaTeX.
#   tar xzf archive.tar.gz && cd ... && make

archive-manuscript: $(MANUSCRIPT_FIGS) $(MANUSCRIPT_INCLUDES) content/manuscript-vars.yml output/content/manuscript.pdf
	bash release/scripts/build_manuscript_archive.sh

# ── Phase 4c — data paper archive (full pipeline) ─────────
# Complete reproducibility package: all corpus-building scripts, DVC pipeline,
# pool data, caches.  Reviewers can verify with:
#   tar xzf archive.tar.gz && cd ... && uv sync && dvc repro
archive-datapaper: check-corpus corpus-tables figures-datapaper
	bash release/scripts/build_datapaper_archive.sh

# ── All checks (tests) ───────────────────────────────────
check:
	$(UV_RUN) pytest tests/ -v --tb=short -n 4

# Fast subset: unit tests only (no Python subprocess spawning, no sleeps, < 10s).
check-fast:
	$(UV_RUN) pytest tests/ -v --tb=short -m "not slow and not integration" -n 4

# Smoke pipeline: run Phase 2 on a 100-row fixture (no DVC pull needed, <30s).
# Exercises: compute_breakpoints, compute_clusters, plot_fig1_bars.
smoke:
	$(UV_RUN) pytest tests/test_smoke_pipeline.py -v --tb=short

# Determinism check: run figure scripts twice on smoke data, diff outputs.
# Catches unseeded randomness, leaking timestamps, floating-point non-determinism.
determinism-check:
	$(UV_RUN) pytest tests/test_determinism.py -v --tb=short

# Regression hashes: compare Phase 2 output hashes against golden baseline.
# Runs as pytest (one test per script, module-scoped fixture = scripts run once).
#   make regression          — check against golden baseline
#   make regression-update   — regenerate golden baseline (after intentional change)
regression:
	$(UV_RUN) pytest tests/test_regression.py -v --tb=short -m integration -k "test_regression_"

regression-update:
	$(UV_RUN) python scripts/compute_regression_hashes.py --update-golden

# ── Benchmarking ─────────────────────────────────────────
# Record wall time + peak RSS per Phase 2 target.
# Output: benchmarks/timings.jsonl (one JSON line per target).
BENCH := scripts/time_target.sh
BENCH_OUT := benchmarks/timings.jsonl

benchmark: check-corpus
	@mkdir -p benchmarks
	$(BENCH) compute_breakpoints $(BENCH_OUT) $(UV_RUN) python scripts/compute_breakpoints.py --output content/tables/tab_breakpoints.csv
	$(BENCH) compute_clusters $(BENCH_OUT) $(UV_RUN) python scripts/compute_clusters.py --output content/tables/tab_alluvial.csv
	$(BENCH) analyze_bimodality $(BENCH_OUT) $(UV_RUN) python scripts/analyze_bimodality.py --output content/tables/tab_bimodality.csv
	$(BENCH) plot_fig1_bars $(BENCH_OUT) $(UV_RUN) python scripts/plot_fig1_bars.py
	@echo "Benchmark results: $(BENCH_OUT)"

# ── Setup (run once after cloning) ───────────────────────
setup:
	git config core.hooksPath hooks
	@echo "Hooks activated (hooks/pre-commit, hooks/post-checkout)"

# ── Housekeeping ─────────────────────────────────────────
clean:
	rm -rf output/

rebuild: clean all
