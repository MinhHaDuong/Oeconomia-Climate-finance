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

# Quarto resolves includes across ALL project files (_quarto.yml render list),
# even when rendering a single document. Every render target needs the full set.
PROJECT_INCLUDES := $(MANUSCRIPT_INCLUDES) $(TECHREP_INCLUDES) \
		$(DATAPAPER_INCLUDES) $(COMPANION_INCLUDES)

# ── Per-document figure sets ─────────────────────────────
MANUSCRIPT_FIGS := content/figures/fig_bars_v1.png content/figures/fig_composition.png

DATAPAPER_FIGS  := content/figures/fig_bars.png content/figures/fig_dag.png

COMPANION_FIGS  := content/figures/fig_breakpoints.png content/figures/fig_alluvial.png \
                   content/figures/fig_breaks.png \
                   content/figures/fig_bimodality.png \
                   content/figures/fig_seed_axis_core.png content/figures/fig_pca_scatter.png \
                   content/figures/fig_genealogy.png

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

ALL_FIGS := $(MANUSCRIPT_FIGS) $(DATAPAPER_FIGS) $(COMPANION_FIGS) $(TECHREP_FIGS)

# ── Default target ────────────────────────────────────────
.PHONY: all setup manuscript papers figures figures-manuscript figures-datapaper figures-companion figures-techrep stats check check-fast smoke benchmark determinism-check check-corpus check-manuscript-data corpus corpus-sync corpus-discover corpus-enrich corpus-extend corpus-filter corpus-align corpus-filter-all corpus-tables corpus-validate deploy-corpus clean rebuild archive-analysis archive-manuscript archive-datapaper analysis-figures analysis-tables analysis-stats manuscript-render manuscript-figures datapaper-render datapaper-figures corpus-handoff

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
	uv run dvc pull --force

# Individual stage aliases.
corpus-discover:
	uv run dvc repro catalog_merge

corpus-enrich:
	uv run dvc repro enrich_dois enrich_abstracts enrich_language summarize_abstracts join_enrichments enrich_citations qa_citations enrich_embeddings

corpus-extend:
	uv run dvc repro extend

corpus-filter:
	uv run dvc repro filter

corpus-filter-all:
	uv run dvc repro extend filter

corpus-align:
	uv run dvc repro align

# Upload artifacts to the DVC remote (padme).
deploy-corpus:
	uv run dvc push

# ── Corpus diagnostics (Phase 1 — reads enrichment caches) ──
content/tables/qa_citations_report.json: scripts/qa_citations.py scripts/utils.py \
		$(DATA_DIR)/citations.csv
	uv run python $<

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
	uv run python -c "import pandas as pd; pd.read_csv('$<').to_feather('$@')"

$(REFINED_CIT_FTH): $(REFINED_CIT)
	uv run python -c "import pandas as pd; pd.read_csv('$<', low_memory=False).to_feather('$@')"

corpus-handoff: check-corpus $(REFINED_FTH) $(REFINED_CIT_FTH)

check-corpus:
	@ok=true; \
	for f in "$(REFINED)" "$(REFINED_EMB)" "$(REFINED_CIT)"; do \
		test -f "$$f" || { echo "MISSING: $$f"; ok=false; }; \
	done; \
	$$ok || { echo "Run 'uv run dvc pull' to sync data, or 'make corpus' to rebuild."; exit 1; }

# Lighter gate for manuscript-only builds (no citations needed).
check-manuscript-data:
	@ok=true; \
	for f in "$(REFINED)" "$(REFINED_EMB)"; do \
		test -f "$$f" || { echo "MISSING: $$f"; ok=false; }; \
	done; \
	$$ok || { echo "Run 'uv run dvc pull' to sync data, or 'make corpus' to rebuild."; exit 1; }

corpus-validate: $(REFINED)
	uv run pytest tests/test_corpus_acceptance.py -v -s --tb=long

# ── Corpus reporting (Phase 2 — reads only refined data) ──
content/tables/tab_citation_coverage.md: scripts/export_citation_coverage.py scripts/utils.py $(REFINED)
	uv run python $<

content/tables/tab_venues.md: scripts/make_tab_venues.py scripts/utils.py $(REFINED) content/tables/tab_pole_papers.csv
	uv run python $<

content/tables/tab_corpus_sources.csv content/tables/tab_corpus_sources.md &: scripts/export_corpus_table.py scripts/utils.py $(REFINED)
	uv run python $<

content/tables/tab_languages.md: scripts/export_language_table.py scripts/utils.py $(ENRICHED)
	uv run python $<

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
		content/tables/tab_axis_detection.csv
	uv run python $<

stats: $(COMPUTED_STATS)

# ── Tables (generated, included by Quarto) ──────────────

# Core subset → venues table
$(MOSTCITED): scripts/build_het_core.py scripts/utils.py $(REFINED)
	uv run python $<

content/tables/tab_core_venues_top10.md: scripts/export_core_venues_markdown.py scripts/summarize_core_venues.py scripts/utils.py $(MOSTCITED)
	uv run python $<

# ── Figures ──────────────────────────────────────────────

# -- Manuscript (Oeconomia article) --
# Fig 1 (bars): corpus growth per year
content/figures/fig_bars.png: scripts/plot_fig1_bars.py scripts/plot_style.py scripts/utils.py $(REFINED)
	uv run python $< --output $@ --no-pdf

# Fig 1 v1 variant: restricted to submission corpus for manuscript stability
content/figures/fig_bars_v1.png: scripts/plot_fig1_bars.py scripts/plot_style.py scripts/utils.py $(REFINED)
	uv run python $< --output $@ --no-pdf --v1-only

# Fig 2 (composition): frozen v1 archive data + corrected labels
content/figures/fig_composition.png: scripts/plot_fig2_composition.py scripts/plot_style.py scripts/utils.py \
		config/v1_tab_alluvial.csv config/v1_cluster_labels.json
	uv run python $< --output $@ --no-pdf --alluvial config/v1_tab_alluvial.csv --labels config/v1_cluster_labels.json

# -- Data paper --
# Semantic UMAP maps (3 co-produced figures)
content/figures/fig_semantic.png content/figures/fig_semantic_lang.png content/figures/fig_semantic_period.png &: \
		scripts/analyze_embeddings.py scripts/utils.py $(REFINED)
	uv run python $<

# -- Companion paper (quantitative) --
# Structural break tables (independent of clustering)
content/tables/tab_breakpoints.csv content/tables/tab_breakpoint_robustness.csv &: \
		scripts/compute_breakpoints.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Clustering + alluvial flow tables — full corpus (companion paper, tech report)
content/tables/tab_alluvial.csv content/tables/cluster_labels.json \
content/tables/tab_core_shares.csv &: \
		scripts/compute_clusters.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Clustering — v1 frozen from reproducibility archive (not re-clustered).
# KMeans is unstable to small corpus perturbations; re-clustering the v1
# subset produces different assignments. These checked-in files are the
# source of truth for manuscript Figure 2.
# To update: copy from the reproducibility archive and commit.

# Breakpoints figure
content/figures/fig_breakpoints.png: \
		scripts/plot_fig_breakpoints.py scripts/utils.py \
		content/tables/tab_breakpoints.csv content/tables/tab_breakpoint_robustness.csv \
		content/tables/tab_alluvial.csv
	uv run python $< --no-pdf

# Alluvial figure
content/figures/fig_alluvial.png: \
		scripts/plot_fig_alluvial.py scripts/utils.py \
		content/tables/tab_alluvial.csv content/tables/cluster_labels.json
	uv run python $< --no-pdf

# Period divergence curves
content/figures/fig_breaks.png: scripts/plot_fig2_breaks.py scripts/plot_style.py scripts/utils.py \
		content/tables/tab_breakpoints.csv
	uv run python $< --no-pdf

# Bimodality tests (co-produced)
content/figures/fig_bimodality.png \
content/figures/fig_bimodality_lexical.png \
content/figures/fig_bimodality_keywords.png \
content/tables/tab_bimodality.csv content/tables/tab_axis_detection.csv \
content/tables/tab_pole_papers.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Seed-axis violin (core, manuscript figure)
content/figures/fig_seed_axis_core.png: scripts/plot_fig_seed_axis.py scripts/plot_style.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# PCA scatter (unsupervised)
content/figures/fig_pca_scatter.png: scripts/plot_fig45_pca_scatter.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Citation genealogy: model (lineage table) then renderers
content/tables/tab_lineages.csv: scripts/analyze_genealogy.py scripts/utils.py \
		$(REFINED) content/tables/tab_pole_papers.csv
	uv run python $<

content/figures/fig_genealogy.png: scripts/plot_genealogy.py scripts/utils.py \
		content/tables/tab_lineages.csv $(REFINED_CIT)
	uv run python $< --no-pdf

content/figures/fig_genealogy.html: scripts/plot_genealogy_html.py scripts/utils.py \
		content/tables/tab_lineages.csv $(REFINED_CIT)
	uv run python $<

# -- Technical report (robustness, variants, supplementary) --
# Core-only: structural break tables
content/tables/tab_breakpoints_core.csv content/tables/tab_breakpoint_robustness_core.csv &: \
		scripts/compute_breakpoints.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# Core-only: clustering + alluvial flow tables
content/tables/tab_alluvial_core.csv content/tables/cluster_labels_core.json &: \
		scripts/compute_clusters.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# Core-only figures
content/figures/fig_breakpoints_core.png: \
		scripts/plot_fig_breakpoints.py scripts/utils.py \
		content/tables/tab_breakpoints_core.csv content/tables/tab_breakpoint_robustness_core.csv \
		content/tables/tab_alluvial_core.csv
	uv run python $< --core-only --no-pdf

content/figures/fig_alluvial_core.png: \
		scripts/plot_fig_alluvial.py scripts/utils.py \
		content/tables/tab_alluvial_core.csv content/tables/cluster_labels_core.json
	uv run python $< --core-only --no-pdf

# Bimodality core variant (co-produced)
content/figures/fig_bimodality_core.png \
content/figures/fig_bimodality_lexical_core.png \
content/figures/fig_bimodality_keywords_core.png \
content/tables/tab_bimodality_core.csv content/tables/tab_axis_detection_core.csv \
content/tables/tab_pole_papers_core.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# Pre-2007 co-citation traditions network
content/figures/fig_traditions.png: scripts/plot_fig_traditions.py scripts/plot_style.py scripts/utils.py $(REFINED)
	uv run python $<

# Co-citation communities (network + community assignments)
content/figures/fig_communities.png \
content/tables/tab_community_summary.csv &: \
		scripts/analyze_cocitation.py scripts/utils.py $(REFINED_CIT)
	uv run python $<

# KDE supplementary
content/figures/fig_kde.png: scripts/plot_figS_kde.py scripts/plot_style.py scripts/utils.py \
		content/tables/tab_pole_papers.csv
	uv run python $< --no-pdf

# Lexical TF-IDF table (diagnostic, not in manuscript)
content/tables/tab_lexical_tfidf.csv: scripts/compute_lexical.py scripts/utils.py $(REFINED) \
		content/tables/tab_breakpoint_robustness.csv
	uv run python $< --no-pdf

# K-sensitivity table (diagnostic, --robustness flag)
content/tables/tab_k_sensitivity.csv: scripts/compute_breakpoints.py scripts/utils.py $(REFINED)
	uv run python $< --robustness --no-pdf

# K-sensitivity figure
content/figures/fig_k_sensitivity.png: scripts/plot_fig_k_sensitivity.py \
		content/tables/tab_k_sensitivity.csv
	uv run python $< --no-pdf

# Lexical TF-IDF figures (one per detected break year; output filenames are
# dynamic, so we use a sentinel file to track freshness).
.lexical_tfidf.stamp: scripts/plot_fig_lexical_tfidf.py scripts/plot_style.py \
		content/tables/tab_lexical_tfidf.csv
	uv run python $< --no-pdf
	@touch $@

# DVC pipeline DAG (data paper)
content/figures/fig_dag.png: scripts/plot_fig_dag.py scripts/plot_style.py dvc.yaml
	uv run python $<

figures-manuscript: corpus-handoff $(MANUSCRIPT_FIGS)
figures-datapaper:  corpus-handoff $(DATAPAPER_FIGS)
figures-companion:  corpus-handoff $(COMPANION_FIGS)
figures-techrep:    corpus-handoff $(TECHREP_FIGS)
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

papers: check-corpus output/content/technical-report.pdf output/content/data-paper.pdf output/content/companion-paper.pdf

# ── Namespaced aliases (Phase 3) ────────────────────────
manuscript-render: manuscript
manuscript-figures: figures-manuscript

datapaper-render: output/content/data-paper.pdf
datapaper-figures: figures-datapaper

output/content/manuscript.pdf: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to pdf

output/content/manuscript.docx: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to docx

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
	uv run pytest tests/ -v --tb=short

# Fast subset: unit tests only (no Python subprocess spawning, no sleeps, < 20s).
check-fast:
	uv run pytest tests/ -v --tb=short -m "not slow and not integration"

# Smoke pipeline: run Phase 2 on a 100-row fixture (no DVC pull needed, <30s).
# Exercises: compute_breakpoints, compute_clusters, plot_fig1_bars.
smoke:
	uv run pytest tests/test_smoke_pipeline.py -v --tb=short

# Determinism check: run figure scripts twice on smoke data, diff outputs.
# Catches unseeded randomness, leaking timestamps, floating-point non-determinism.
determinism-check:
	uv run pytest tests/test_determinism.py -v --tb=short

# ── Benchmarking ─────────────────────────────────────────
# Record wall time + peak RSS per Phase 2 target.
# Output: benchmarks/timings.jsonl (one JSON line per target).
BENCH := scripts/time_target.sh
BENCH_OUT := benchmarks/timings.jsonl

benchmark: check-corpus
	@mkdir -p benchmarks
	$(BENCH) compute_breakpoints $(BENCH_OUT) uv run python scripts/compute_breakpoints.py --no-pdf
	$(BENCH) compute_clusters $(BENCH_OUT) uv run python scripts/compute_clusters.py --no-pdf
	$(BENCH) analyze_bimodality $(BENCH_OUT) uv run python scripts/analyze_bimodality.py --no-pdf
	$(BENCH) plot_fig1_bars $(BENCH_OUT) uv run python scripts/plot_fig1_bars.py --no-pdf
	@echo "Benchmark results: $(BENCH_OUT)"

# ── Setup (run once after cloning) ───────────────────────
setup:
	git config core.hooksPath hooks
	@echo "Hooks activated (hooks/pre-commit, hooks/post-checkout)"

# ── Housekeeping ─────────────────────────────────────────
clean:
	rm -rf output/

rebuild: clean all
