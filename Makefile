# Makefile — Counting Climate Finance (Œconomia)
#
# Three-phase pipeline:
#   Phase 1: make corpus       Corpus building (slow — API calls, run rarely)
#   Phase 2: make figures      Analysis & figures (fast, deterministic, run often)
#   Phase 3: make manuscript   Render documents (Quarto → PDF/DOCX)
#
# Usage:
#   make              Build all documents (manuscript + 3 companion papers)
#   make manuscript   Build manuscript only (PDF + DOCX)
#   make papers       Build technical report, data paper, companion paper
#   make figures      Regenerate all figures (from existing data)
#   make archive-manuscript  Minimal package for Oeconomia reviewers
#   make archive-datapaper   Full pipeline package for data paper
#   make clean        Remove build outputs
#   make rebuild      Clean + rebuild everything

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
		content/_includes/corpus-refinement.md \
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
		content/_includes/corpus-refinement.md \
		content/_includes/embedding-generation.md \
		content/_includes/reproducibility.md

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
MANUSCRIPT_FIGS := content/figures/fig_bars.png content/figures/fig_composition.png

DATAPAPER_FIGS  := content/figures/fig_bars.png content/figures/fig_dag.png

COMPANION_FIGS  := content/figures/fig_breakpoints.png content/figures/fig_alluvial.png \
                   content/figures/fig_breaks.png \
                   content/figures/fig_bimodality.png \
                   content/figures/fig_seed_axis_core.png content/figures/fig_pca_scatter.png \
                   content/figures/fig_genealogy.png

TECHREP_FIGS    := content/figures/fig_alluvial_core.png \
                   content/figures/fig_bimodality_core.png \
                   content/figures/fig_kde.png

ALL_FIGS := $(MANUSCRIPT_FIGS) $(DATAPAPER_FIGS) $(COMPANION_FIGS) $(TECHREP_FIGS)

# ── Default target ────────────────────────────────────────
.PHONY: all setup manuscript papers figures figures-manuscript figures-datapaper figures-companion figures-techrep stats check check-fast check-corpus check-manuscript-data corpus corpus-sync corpus-discover corpus-enrich corpus-extend corpus-filter corpus-align corpus-refine corpus-tables corpus-validate deploy-corpus lint-prose clean rebuild archive-analysis archive-manuscript archive-datapaper

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
corpus:
	@[ "$$(hostname)" = "padme" ] || { echo "error: make corpus runs on padme only. Use 'make corpus-sync' on $$(hostname)."; exit 1; }
	@uv run dvc version >/dev/null 2>&1 || { echo "error: dvc not found. Install with: uv tool install 'dvc[ssh]'"; exit 1; }
	uv run dvc repro; ret=$$?; uv run dvc push; exit $$ret

# Sync data from padme — run on doudou (never pushes).
corpus-sync:
	@[ "$$(hostname)" != "padme" ] || { echo "error: use 'make corpus' on padme, not corpus-sync."; exit 1; }
	git pull
	uv run dvc pull --force

# Individual stage aliases.
corpus-discover:
	uv run dvc repro catalog_merge

corpus-enrich:
	uv run dvc repro enrich_works enrich_citations qa_citations enrich_embeddings

corpus-extend:
	uv run dvc repro extend

corpus-filter:
	uv run dvc repro filter

corpus-refine:
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

content/tables/tab_corpus_sources.csv: scripts/export_corpus_table.py scripts/utils.py $(REFINED)
	uv run python $<

corpus-tables: content/tables/tab_corpus_sources.csv \
               content/tables/tab_citation_coverage.md

# ── Statistics (computed from pipeline outputs) ──────────
STATS := content/manuscript-vars.yml content/technical-report-vars.yml \
         content/data-paper-vars.yml content/companion-paper-vars.yml

# Grouped target (&:) — one invocation writes all 4 files. Requires GNU Make >= 4.3.
$(STATS) &: scripts/compute_vars.py scripts/utils.py $(REFINED) \
		content/tables/tab_bimodality.csv content/tables/tab_bimodality_core.csv \
		content/tables/tab_axis_detection.csv
	uv run python $<

stats: $(STATS)

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
	uv run python $< --no-pdf

# Fig 2 (composition): thematic clusters across periods
content/figures/fig_composition.png: scripts/plot_fig2_composition.py scripts/plot_style.py scripts/utils.py \
		content/tables/tab_alluvial.csv
	uv run python $< --no-pdf

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

# Clustering + alluvial flow tables (independent of break detection)
content/tables/tab_alluvial.csv content/tables/cluster_labels.json \
content/tables/tab_core_shares.csv &: \
		scripts/compute_clusters.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

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

# Citation genealogy (needs bimodality output for pole assignments)
content/figures/fig_genealogy.png: scripts/analyze_genealogy.py scripts/utils.py \
		$(REFINED) content/tables/tab_pole_papers.csv
	uv run python $< --no-pdf

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
content/tables/tab_bimodality_core.csv content/tables/tab_axis_detection_core.csv \
content/tables/tab_pole_papers_core.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

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

# Lexical TF-IDF figures (one per detected break year; .PHONY because output
# filenames are dynamic — they depend on detected break years, so make cannot
# declare them as static targets)
.PHONY: lexical-figures
lexical-figures: content/tables/tab_lexical_tfidf.csv
	uv run python scripts/plot_fig_lexical_tfidf.py --no-pdf

# DVC pipeline DAG (data paper)
content/figures/fig_dag.png: scripts/plot_fig_dag.py scripts/plot_style.py dvc.yaml
	uv run python $<

figures-manuscript: check-manuscript-data $(MANUSCRIPT_FIGS)
figures-datapaper:  check-corpus $(DATAPAPER_FIGS)
figures-companion:  check-corpus $(COMPANION_FIGS)
figures-techrep:    check-corpus $(TECHREP_FIGS)
figures: check-corpus $(ALL_FIGS) corpus-tables

# ═══════════════════════════════════════════════════════════
# PHASE 3 — Render (Quarto → PDF/DOCX)
# ═══════════════════════════════════════════════════════════

manuscript: output/content/manuscript.pdf output/content/manuscript.docx

papers: output/content/technical-report.pdf output/content/data-paper.pdf output/content/companion-paper.pdf

output/content/manuscript.pdf: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to pdf

output/content/manuscript.docx: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(PROJECT_INCLUDES) content/manuscript-vars.yml
	quarto render $< --to docx

output/content/technical-report.pdf: content/technical-report.qmd $(PROJECT_INCLUDES) $(BIB) $(STATS)
	quarto render $< --to pdf

output/content/data-paper.pdf: content/data-paper.qmd $(PROJECT_INCLUDES) $(BIB) $(STATS)
	quarto render $< --to pdf

output/content/companion-paper.pdf: content/companion-paper.qmd $(PROJECT_INCLUDES) $(BIB) $(STATS)
	quarto render $< --to pdf

# ── Phase 2 archive (analysis reproducibility) ────────────
# Data + scripts: reviewers verify figures/tables are reproducible.
#   tar xzf archive.tar.gz && cd ... && uv sync && make
SHELL            := /bin/bash
ANALYSIS_ARCHIVE := climate-finance-analysis
ANALYSIS_TMP     := /tmp/$(ANALYSIS_ARCHIVE)
ANALYSIS_OUTPUTS := content/figures/fig_bars.png \
                    content/figures/fig_composition.png \
                    content/tables/tab_venues.md \
                    content/tables/tab_alluvial.csv \
                    content/tables/tab_core_shares.csv \
                    content/tables/tab_bimodality.csv \
                    content/tables/tab_axis_detection.csv \
                    content/tables/tab_pole_papers.csv \
                    content/tables/cluster_labels.json

archive-analysis: check-manuscript-data $(ANALYSIS_OUTPUTS)
	@echo "=== Building analysis archive ==="
	rm -rf $(ANALYSIS_TMP)
	mkdir -p $(ANALYSIS_TMP)/data/catalogs \
	         $(ANALYSIS_TMP)/scripts \
	         $(ANALYSIS_TMP)/config \
	         $(ANALYSIS_TMP)/content/figures \
	         $(ANALYSIS_TMP)/content/tables
	@# Phase 1 contract data (dereference DVC symlinks)
	cp -L $(DATA_DIR)/refined_works.csv     $(ANALYSIS_TMP)/data/catalogs/
	cp -L $(DATA_DIR)/refined_embeddings.npz $(ANALYSIS_TMP)/data/catalogs/
	@# Scripts needed to build figures + tables
	cp scripts/utils.py                     $(ANALYSIS_TMP)/scripts/
	cp scripts/plot_style.py                $(ANALYSIS_TMP)/scripts/
	cp scripts/plot_fig1_bars.py            $(ANALYSIS_TMP)/scripts/
	cp scripts/plot_fig2_composition.py     $(ANALYSIS_TMP)/scripts/
	cp scripts/compute_clusters.py          $(ANALYSIS_TMP)/scripts/
	cp scripts/build_het_core.py            $(ANALYSIS_TMP)/scripts/
	cp scripts/export_core_venues_markdown.py $(ANALYSIS_TMP)/scripts/
	cp scripts/summarize_core_venues.py     $(ANALYSIS_TMP)/scripts/
	cp scripts/make_tab_venues.py           $(ANALYSIS_TMP)/scripts/
	cp scripts/export_citation_coverage.py  $(ANALYSIS_TMP)/scripts/
	cp scripts/analyze_bimodality.py        $(ANALYSIS_TMP)/scripts/
	@# Config + build infrastructure
	cp config/analysis.yaml             $(ANALYSIS_TMP)/config/
	cp Makefile.analysis-manuscript                $(ANALYSIS_TMP)/Makefile
	cp pyproject.toml uv.lock           $(ANALYSIS_TMP)/
	echo 'CLIMATE_FINANCE_DATA=data' > $(ANALYSIS_TMP)/.env
	@# README + container file for reviewers
	cp README-analysis.md $(ANALYSIS_TMP)/README.md
	cp Dockerfile.analysis $(ANALYSIS_TMP)/Dockerfile
	@# Expected output checksums — reviewers verify with: make && make verify
	md5sum $(ANALYSIS_OUTPUTS) > $(ANALYSIS_TMP)/expected_outputs.md5
	@echo "=== Creating tarball ==="
	tar czf $(ANALYSIS_ARCHIVE).tar.gz -C /tmp $(ANALYSIS_ARCHIVE)
	@echo "=== Analysis archive ==="
	@du -h $(ANALYSIS_ARCHIVE).tar.gz
	@echo "Files: $$(tar tzf $(ANALYSIS_ARCHIVE).tar.gz | wc -l)"
	rm -rf $(ANALYSIS_TMP)
	@echo "Done: $(ANALYSIS_ARCHIVE).tar.gz"

# ── Phase 3 archive (manuscript reproducibility) ──────────
# Pre-built figures + content: reviewers verify PDF renders.
# No Python needed — only Quarto + XeLaTeX.
#   tar xzf archive.tar.gz && cd ... && make
MANU_ARCHIVE     := climate-finance-manuscript
MANU_TMP         := /tmp/$(MANU_ARCHIVE)

archive-manuscript: $(MANUSCRIPT_FIGS) $(MANUSCRIPT_INCLUDES) content/manuscript-vars.yml output/content/manuscript.pdf
	@echo "=== Building manuscript archive ==="
	rm -rf $(MANU_TMP)
	mkdir -p $(MANU_TMP)/content/bibliography \
	         $(MANU_TMP)/content/tables \
	         $(MANU_TMP)/content/figures
	@# Pre-built figures (validated, not regenerated)
	cp content/figures/fig_bars.png         $(MANU_TMP)/content/figures/
	cp content/figures/fig_composition.png  $(MANU_TMP)/content/figures/
	@# Manuscript content
	cp content/manuscript.qmd               $(MANU_TMP)/content/
	cp content/manuscript-vars.yml          $(MANU_TMP)/content/
	cp content/author-footnote.tex          $(MANU_TMP)/content/
	cp content/tables/tab_venues.md         $(MANU_TMP)/content/tables/
	cp content/bibliography/main.bib        $(MANU_TMP)/content/bibliography/
	cp content/bibliography/oeconomia.csl   $(MANU_TMP)/content/bibliography/
	@# Pre-built output PDF (at root, away from Quarto's clean scope)
	cp output/content/manuscript.pdf    $(MANU_TMP)/expected-manuscript.pdf
	@# Build infrastructure (no Python needed)
	cp Makefile.manuscript              $(MANU_TMP)/Makefile
	cp _quarto.yml                      $(MANU_TMP)/
	@# README for reviewers
	cp README-manuscript.md $(MANU_TMP)/README.md
	@# Record toolchain versions used to build the shipped PDF
	printf 'Quarto %s\n%s\n' "$$(quarto --version)" "$$(xdvipdfmx --version 2>&1 | head -1)" > $(MANU_TMP)/TOOLCHAIN.txt
	@# Input checksums — reviewers verify with: make && make verify
	cd $(MANU_TMP) && md5sum content/figures/*.png content/tables/*.md \
	    content/bibliography/main.bib content/manuscript.qmd \
	    content/manuscript-vars.yml > checksums.md5
	@echo "=== Creating tarball ==="
	tar czf $(MANU_ARCHIVE).tar.gz -C /tmp $(MANU_ARCHIVE)
	@echo "=== Manuscript archive ==="
	@du -h $(MANU_ARCHIVE).tar.gz
	@echo "Files: $$(tar tzf $(MANU_ARCHIVE).tar.gz | wc -l)"
	rm -rf $(MANU_TMP)
	@echo "Done: $(MANU_ARCHIVE).tar.gz"

# ── Data paper archive (full pipeline) ────────────────────
# Complete reproducibility package: all corpus-building scripts, DVC pipeline,
# pool data, caches.  Reviewers can verify with:
#   tar xzf archive.tar.gz && cd ... && uv sync && dvc repro
DPAPER_ARCHIVE   := climate-finance-datapaper
DPAPER_TMP       := /tmp/$(DPAPER_ARCHIVE)

archive-datapaper: check-corpus
	@echo "=== Building data paper archive ==="
	rm -rf $(DPAPER_TMP)
	mkdir -p $(DPAPER_TMP)
	@# Start with everything git tracks (excludes .git, respects .gitignore)
	git archive HEAD | tar -x -C $(DPAPER_TMP)
	@# Copy all DVC-managed data (dereference symlinks)
	@echo "  Copying DVC-managed data (this may take a while)..."
	cp -rL data/ $(DPAPER_TMP)/data/
	@# Copy generated figures if they exist
	@if ls content/figures/*.png >/dev/null 2>&1; then \
		mkdir -p $(DPAPER_TMP)/content/figures; \
		cp content/figures/*.png $(DPAPER_TMP)/content/figures/; \
	fi
	@# Copy generated tables if they exist
	@if ls content/tables/* >/dev/null 2>&1; then \
		mkdir -p $(DPAPER_TMP)/content/tables; \
		cp -r content/tables/* $(DPAPER_TMP)/content/tables/; \
	fi
	@# Copy per-document vars files (gitignored, like figures/tables)
	cp content/*-vars.yml $(DPAPER_TMP)/content/ 2>/dev/null || true
	@# .env template
	echo 'CLIMATE_FINANCE_DATA=data' > $(DPAPER_TMP)/.env
	@# Remove items that should not ship
	rm -rf $(DPAPER_TMP)/.dvc $(DPAPER_TMP)/attic $(DPAPER_TMP)/.claude
	@echo "=== Creating tarball ==="
	tar czf $(DPAPER_ARCHIVE).tar.gz -C /tmp \
		--exclude='__pycache__' --exclude='.venv' \
		$(DPAPER_ARCHIVE)
	@echo "=== Data paper archive ==="
	@du -h $(DPAPER_ARCHIVE).tar.gz
	@echo "Files: $$(tar tzf $(DPAPER_ARCHIVE).tar.gz | wc -l)"
	rm -rf $(DPAPER_TMP)
	@echo "Done: $(DPAPER_ARCHIVE).tar.gz"

# ── All checks (tests + lint) ────────────────────────────
check: lint-prose
	uv run pytest tests/ -v --tb=short

# Fast subset: unit tests only (no corpus data or network needed, < 30s).
check-fast: lint-prose
	uv run pytest tests/ -v --tb=short -m "not slow"

# ── Prose linting (AI-tell detection) ─────────────────────
lint-prose:
	@echo "=== Blacklisted words (expect 0) ==="
	@count=$$(grep -ciE 'delve|nuanced|multifaceted|pivotal|tapestry|intricate|meticulous|vibrant|showcasing|underscores' content/manuscript.qmd || true); \
	echo "  Found: $$count"; [ "$$count" -eq 0 ] || exit 1
	@echo "=== Em-dash heavy paragraphs (target 0, currently 7 — fix during proofread) ==="
	@count=$$(grep -cP -- '---.*---.*---' content/manuscript.qmd || true); \
	echo "  Found: $$count"; [ "$$count" -le 7 ] || exit 1
	@echo "=== Contrast farming (expect ≤3) ==="
	@count=$$(grep -cP 'not .{3,60}, but ' content/manuscript.qmd || true); \
	echo "  Found: $$count"; [ "$$count" -le 3 ] || exit 1
	@echo "LINT-PROSE: PASS"

# ── Setup (run once after cloning) ───────────────────────
setup:
	git config core.hooksPath hooks
	@echo "Hooks activated (hooks/pre-commit, hooks/post-checkout)"

# ── Housekeeping ─────────────────────────────────────────
clean:
	rm -rf output/

rebuild: clean all
