# Makefile — Counting Climate Finance (Œconomia)
#
# Usage:
#   make            Build all documents (manuscript + 3 companion papers)
#   make manuscript Build manuscript only (PDF + DOCX)
#   make papers     Build technical report, data paper, companion paper
#   make figures    Regenerate all figures (from existing data)
#   make figures-manuscript  Figures for the Oeconomia article only
#   make figures-datapaper   Figures for the data descriptor
#   make figures-companion   Figures for the quantitative paper
#   make figures-techrep     Figures for the technical report (robustness)
#   make data       Run slow API collection scripts
#   make archive    Package code + data, validate, create tarball
#   make clean      Remove build outputs
#   make rebuild    Clean + rebuild everything

# ── Paths ─────────────────────────────────────────────────
# Machine-specific path set in .env (see .env.example).
# Python scripts read the same file via utils.py.
-include .env
export CLIMATE_FINANCE_DATA
DATA_DIR     ?= $(CLIMATE_FINANCE_DATA)/catalogs
BIB         := content/bibliography/main.bib
CSL         := content/bibliography/oeconomia.csl
SRC         := content/manuscript.qmd

REFINED     := $(DATA_DIR)/refined_works.csv
MOSTCITED   := $(DATA_DIR)/het_mostcited_50.csv
ECON_YEARLY := $(DATA_DIR)/openalex_econ_yearly.csv
OVERLAP     := $(DATA_DIR)/openalex_econ_fin_overlap.csv

# ── Reproducibility ───────────────────────────────────────
# PYTHONHASHSEED=0  → deterministic dict/set iteration order
# SOURCE_DATE_EPOCH=0 → reproducible timestamps in PDF/PNG metadata
export PYTHONHASHSEED := 0
export SOURCE_DATE_EPOCH := 0

# ── Quarto ───────────────────────────────────────────────
INCLUDES    := $(wildcard content/_includes/*.md)

# ── Per-document figure sets ─────────────────────────────
MANUSCRIPT_FIGS := content/figures/fig_bars.png content/figures/fig_composition.png

DATAPAPER_FIGS  := content/figures/fig_emergence.png \
                   content/figures/fig_semantic.png

COMPANION_FIGS  := content/figures/fig_breakpoints.png content/figures/fig_alluvial.png \
                   content/figures/fig_breaks.png \
                   content/figures/fig_bimodality.png \
                   content/figures/fig_seed_axis_core.png content/figures/fig_pca_scatter.png \
                   content/figures/fig_genealogy.png \
                   content/figures/fig_robustness.png

TECHREP_FIGS    := content/figures/fig_alluvial_core.png \
                   content/figures/fig_bimodality_core.png \
                   content/figures/fig_kde.png

ALL_FIGS := $(MANUSCRIPT_FIGS) $(DATAPAPER_FIGS) $(COMPANION_FIGS) $(TECHREP_FIGS)

# ── Default target ────────────────────────────────────────
.PHONY: all manuscript papers figures figures-manuscript figures-datapaper figures-companion figures-techrep data citations corpus corpus-discover corpus-enrich corpus-refine deploy-corpus clean rebuild archive verify-remote

all: manuscript papers

manuscript: output/content/manuscript.pdf output/content/manuscript.docx

papers: output/content/technical-report.pdf output/content/data-paper.pdf output/content/companion-paper.pdf

# ── Tables (generated, included by Quarto) ──────────────
MANUSCRIPT_TABLES := content/tables/tab_core_venues_top10.md

# Core subset → venues table
$(MOSTCITED): scripts/build_het_core.py scripts/utils.py $(REFINED)
	uv run python $<

content/tables/tab_core_venues_top10.md: scripts/export_core_venues_markdown.py scripts/summarize_core_venues.py scripts/utils.py $(MOSTCITED)
	uv run python $<

# ── Manuscript ───────────────────────────────────────────
output/content/manuscript.pdf: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(MANUSCRIPT_TABLES) $(INCLUDES)
	quarto render $< --to pdf

output/content/manuscript.docx: $(SRC) $(BIB) $(CSL) $(MANUSCRIPT_FIGS) $(MANUSCRIPT_TABLES) $(INCLUDES)
	quarto render $< --to docx

# ── Companion documents ─────────────────────────────────
output/content/technical-report.pdf: content/technical-report.qmd $(INCLUDES) $(BIB)
	quarto render $< --to pdf

output/content/data-paper.pdf: content/data-paper.qmd $(INCLUDES) $(BIB)
	quarto render $< --to pdf

output/content/companion-paper.pdf: content/companion-paper.qmd $(INCLUDES) $(BIB)
	quarto render $< --to pdf

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
# Emergence (economics total + CF share)
content/figures/fig_emergence.png: scripts/plot_fig1_emergence.py scripts/plot_helpers.py $(ECON_YEARLY)
	uv run python $< --no-pdf

# Semantic UMAP maps (3 co-produced figures)
content/figures/fig_semantic.png content/figures/fig_semantic_lang.png content/figures/fig_semantic_period.png &: \
		scripts/analyze_embeddings.py scripts/utils.py $(REFINED)
	uv run python $<

# -- Companion paper (quantitative) --
# Breakpoints + alluvial (co-produced by one script run)
content/figures/fig_alluvial.png content/figures/fig_breakpoints.png &: \
		scripts/analyze_alluvial.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Period divergence curves
content/figures/fig_breaks.png: scripts/plot_fig2_breaks.py scripts/plot_style.py scripts/utils.py \
		content/tables/tab_breakpoints.csv
	uv run python $< --no-pdf

# Bimodality tests (co-produced)
content/figures/fig_bimodality.png content/tables/tab_pole_papers.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# PCA seed-axis scatter (core, supervised)
content/figures/fig_seed_axis_core.png: scripts/plot_fig45_pca_scatter.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --supervised --no-pdf

# PCA scatter (unsupervised)
content/figures/fig_pca_scatter.png: scripts/plot_fig45_pca_scatter.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Citation genealogy (needs bimodality output for pole assignments)
content/figures/fig_genealogy.png: scripts/analyze_genealogy.py scripts/utils.py \
		$(REFINED) content/tables/tab_pole_papers.csv
	uv run python $< --no-pdf

# Robustness (econ vs finance vs RePEc)
content/figures/fig_robustness.png: scripts/plot_fig1_robustness.py scripts/plot_helpers.py \
		$(ECON_YEARLY) $(OVERLAP)
	uv run python $< --no-pdf

# -- Technical report (robustness, variants, supplementary) --
# Core-only variants (co-produced)
content/figures/fig_alluvial_core.png content/figures/fig_breakpoints_core.png &: \
		scripts/analyze_alluvial.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# Bimodality core variant
content/figures/fig_bimodality_core.png: scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# KDE supplementary
content/figures/fig_kde.png: scripts/plot_figS_kde.py scripts/plot_style.py scripts/utils.py \
		content/tables/tab_pole_papers.csv
	uv run python $< --no-pdf

figures-manuscript: $(MANUSCRIPT_FIGS)
figures-datapaper:  $(DATAPAPER_FIGS)
figures-companion:  $(COMPANION_FIGS)
figures-techrep:    $(TECHREP_FIGS)
figures: $(ALL_FIGS)

# ── Corpus pipeline (slow — downloads from APIs) ─────────
# Three phases: discover → enrich → refine
# Hand-harvested CSVs (bibcnrs_works.csv, scispsace_works.csv) must be
# pre-placed in $(DATA_DIR) before running.
corpus: corpus-discover corpus-enrich corpus-refine

# Phase 1: Discovery + merge + cheap filter (flags 1-3 only)
corpus-discover:
	uv run python scripts/catalog_istex.py --api
	uv run python scripts/catalog_openalex.py --resume
	uv run python scripts/catalog_semanticscholar.py --resume
	uv run python scripts/catalog_grey.py
	uv run python scripts/catalog_merge.py
	uv run python scripts/build_teaching_canon.py
	uv run python scripts/catalog_merge.py
	uv run python scripts/corpus_refine.py --apply --cheap

# Phase 2: Enrich abstracts + citations (parallel), then embeddings
# Abstracts and citations are independent; embeddings need abstracts.
# Requires: uv sync --group corpus  (torch, sentence-transformers, hdbscan, …)
corpus-enrich:
	uv run python scripts/enrich_abstracts.py
	uv run python scripts/enrich_citations_batch.py
	uv run python scripts/enrich_citations_openalex.py
	uv run python scripts/qc_citations.py
	uv run python scripts/analyze_embeddings.py

# Phase 3: Full refinement with all 6 flags
corpus-refine:
	uv run python scripts/corpus_refine.py --apply

deploy-corpus:
	ssh $(REMOTE_HOST) 'bash -l -c "\
	  cd ~/Oeconomia-Climate-finance && \
	  git pull && \
	  uv sync && \
	  nohup make corpus > corpus.log 2>&1 &"'
	@echo "Corpus pipeline started on $(REMOTE_HOST). Monitor with:"
	@echo "  ssh $(REMOTE_HOST) 'tail -f ~/Oeconomia-Climate-finance/corpus.log'"

# ── Data collection (slow — not in default target) ───────
data: citations
	uv run python scripts/count_openalex_econ_cf.py
	uv run python scripts/count_openalex_econ_cf.py --scope finance
	uv run python scripts/count_openalex_econ_fin_overlap.py
	uv run python scripts/count_repec_econ_cf.py

# Citation enrichment: run Crossref first, then OpenAlex to fill the gap.
# Both scripts are resumable; re-running only fetches what's missing.
citations:
	uv run python scripts/enrich_citations_batch.py
	uv run python scripts/enrich_citations_openalex.py
	uv run python scripts/qc_citations.py

# ── Replication archive ─────────────────────────────────
SHELL := /bin/bash
ARCHIVE_NAME := climate-finance-replication
ARCHIVE_DATA := refined_works.csv embeddings.npy semantic_clusters.csv \
                citations.csv openalex_econ_yearly.csv \
                openalex_econ_fin_overlap.csv openalex_finance_yearly.csv \
                repec_econ_yearly.csv
ARCHIVE_TMP  := /tmp/$(ARCHIVE_NAME)

archive: figures
	@echo "=== Building replication archive ==="
	rm -rf $(ARCHIVE_TMP)
	mkdir -p $(ARCHIVE_TMP)/data/catalogs
	git archive HEAD | tar -x -C $(ARCHIVE_TMP)
	rm -rf $(ARCHIVE_TMP)/content/figures $(ARCHIVE_TMP)/content/tables
	$(foreach f,$(ARCHIVE_DATA),cp $(DATA_DIR)/$(f) $(ARCHIVE_TMP)/data/catalogs/;)
	@echo "=== Validating: uv sync + make figures ==="
	cd $(ARCHIVE_TMP) && uv sync --quiet --no-group corpus
	cd $(ARCHIVE_TMP) && CLIMATE_FINANCE_DATA=$(ARCHIVE_TMP)/data \
		$(MAKE) DATA_DIR=$(ARCHIVE_TMP)/data/catalogs figures
	@echo "=== Comparing checksums (figures in both) ==="
	@fail=0; for f in content/figures/*.png; do \
	  if [ -f "$(ARCHIVE_TMP)/$$f" ]; then \
	    a=$$(md5sum "$$f" | cut -d' ' -f1); \
	    b=$$(md5sum "$(ARCHIVE_TMP)/$$f" | cut -d' ' -f1); \
	    if [ "$$a" != "$$b" ]; then echo "MISMATCH: $$f"; fail=1; fi; \
	  fi; \
	done; [ $$fail -eq 0 ] && echo "FIGURES: PASS" || { echo "FIGURES: FAIL"; exit 1; }
	@fail=0; for f in content/tables/*.csv; do \
	  if [ -f "$(ARCHIVE_TMP)/$$f" ]; then \
	    a=$$(md5sum "$$f" | cut -d' ' -f1); \
	    b=$$(md5sum "$(ARCHIVE_TMP)/$$f" | cut -d' ' -f1); \
	    if [ "$$a" != "$$b" ]; then echo "MISMATCH: $$f"; fail=1; fi; \
	  fi; \
	done; [ $$fail -eq 0 ] && echo "TABLES: PASS" || { echo "TABLES: FAIL"; exit 1; }
	@echo "=== Creating tarball ==="
	tar czf $(ARCHIVE_NAME).tar.gz -C /tmp \
		--exclude='.venv' --exclude='__pycache__' \
		--exclude='content/figures' --exclude='content/tables' \
		$(ARCHIVE_NAME)
	@du -h $(ARCHIVE_NAME).tar.gz
	rm -rf $(ARCHIVE_TMP)
	@echo "Done: $(ARCHIVE_NAME).tar.gz"

# ── Remote verification ─────────────────────────────────
REMOTE_HOST ?= padme
REMOTE_DIR  := /tmp/$(ARCHIVE_NAME)

verify-remote: $(ARCHIVE_NAME).tar.gz
	@echo "=== Uploading to $(REMOTE_HOST) ==="
	scp $(ARCHIVE_NAME).tar.gz $(REMOTE_HOST):/tmp/
	@echo "=== Running on $(REMOTE_HOST) ==="
	ssh $(REMOTE_HOST) 'bash -l -c "\
	  cd /tmp && rm -rf $(ARCHIVE_NAME) && \
	  tar xzf $(ARCHIVE_NAME).tar.gz && \
	  cd $(ARCHIVE_NAME) && \
	  uv sync --quiet --no-group corpus && \
	  CLIMATE_FINANCE_DATA=$(REMOTE_DIR)/data make DATA_DIR=$(REMOTE_DIR)/data/catalogs figures && \
	  echo === Checksums === && \
	  md5sum content/figures/*.png content/tables/*.csv | sort -k2"'
	@echo "=== Local checksums ==="
	@md5sum content/figures/*.png content/tables/*.csv | sort -k2
	@echo "=== Compare visually or diff the above ==="

# ── Housekeeping ─────────────────────────────────────────
clean:
	rm -rf output/

rebuild: clean all
