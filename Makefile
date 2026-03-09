# Makefile — Counting Climate Finance (Œconomia)
#
# Usage:
#   make            Build all documents (manuscript + 3 companion papers)
#   make manuscript Build manuscript only (PDF + DOCX)
#   make papers     Build technical report, data paper, companion paper
#   make figures    Regenerate all figures (from existing data)
#   make data       Run slow API collection scripts
#   make archive    Package code + data, validate, create tarball
#   make clean      Remove build outputs
#   make rebuild    Clean + rebuild everything

# ── Paths ─────────────────────────────────────────────────
# Scripts find data via scripts/utils.py (CLIMATE_FINANCE_DATA env var
# or ~/data/projets/Oeconomia-Climate-finance/).  DATA_DIR here is only
# for Make's timestamp-based dependency tracking.
DATA_DIR    ?= $(HOME)/data/projets/Oeconomia-Climate-finance/catalogs
BIB         := content/bibliography/main.bib
CSL         := content/bibliography/oeconomia.csl
SRC         := content/manuscript.qmd

REFINED     := $(DATA_DIR)/refined_works.csv
ECON_YEARLY := $(DATA_DIR)/openalex_econ_yearly.csv
OVERLAP     := $(DATA_DIR)/openalex_econ_fin_overlap.csv

# ── Reproducibility ───────────────────────────────────────
# PYTHONHASHSEED=0  → deterministic dict/set iteration order
# SOURCE_DATE_EPOCH=0 → reproducible timestamps in PDF/PNG metadata
export PYTHONHASHSEED := 0
export SOURCE_DATE_EPOCH := 0

# ── Quarto ───────────────────────────────────────────────
INCLUDES    := $(wildcard content/_includes/*.md)

# ── Default target ────────────────────────────────────────
.PHONY: all manuscript papers figures data citations clean rebuild archive verify-remote

all: manuscript papers

manuscript: output/content/manuscript.pdf output/content/manuscript.docx

papers: output/content/technical-report.pdf output/content/data-paper.pdf output/content/companion-paper.pdf

# ── Manuscript ───────────────────────────────────────────
output/content/manuscript.pdf: $(SRC) $(BIB) $(CSL) content/figures/fig1_emergence.png content/figures/fig3_alluvial.png
	quarto render $< --to pdf

output/content/manuscript.docx: $(SRC) $(BIB) $(CSL) content/figures/fig1_emergence.png content/figures/fig3_alluvial.png
	quarto render $< --to docx

# ── Companion documents ─────────────────────────────────
output/content/technical-report.pdf: content/technical-report.qmd $(INCLUDES) $(BIB)
	quarto render $< --to pdf

output/content/data-paper.pdf: content/data-paper.qmd $(INCLUDES) $(BIB)
	quarto render $< --to pdf

output/content/companion-paper.pdf: content/companion-paper.qmd $(INCLUDES) $(BIB)
	quarto render $< --to pdf

# ── Figures (Stage 1) ────────────────────────────────────
# Fig 1: emergence (economics total + CF share)
content/figures/fig1_emergence.png: scripts/plot_fig1_emergence.py scripts/plot_helpers.py $(ECON_YEARLY)
	uv run python $< --no-pdf

# Figs 2+3: breakpoints + alluvial (co-produced by one script run)
content/figures/fig3_alluvial.png content/figures/fig2_breakpoints.png &: \
		scripts/analyze_alluvial.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Figs 2b+3b: core-only variants (co-produced)
content/figures/fig3b_alluvial_core.png content/figures/fig2b_breakpoints_core.png &: \
		scripts/analyze_alluvial.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --no-pdf

# Fig 4: citation genealogy (needs bimodality output for pole assignments)
content/figures/fig4_genealogy.png: scripts/analyze_genealogy.py scripts/utils.py \
		$(REFINED) content/tables/tab5_pole_papers.csv
	uv run python $< --no-pdf

# Fig 4 alt: PCA seed-axis scatter (core, supervised)
content/figures/fig4_seed_axis_core.png: scripts/plot_fig45_pca_scatter.py scripts/utils.py $(REFINED)
	uv run python $< --core-only --supervised --no-pdf

# Figs 5a/5b/5c: bimodality tests (co-produced)
content/figures/fig5a_bimodality.png content/tables/tab5_pole_papers.csv &: \
		scripts/analyze_bimodality.py scripts/utils.py $(REFINED)
	uv run python $< --no-pdf

# Fig A.1a: robustness (econ vs finance vs RePEc)
content/figures/figA_1a_robustness.png: scripts/plot_fig1_robustness.py scripts/plot_helpers.py \
		$(ECON_YEARLY) $(OVERLAP)
	uv run python $< --no-pdf

# Aggregate
MANUSCRIPT_FIGS := content/figures/fig1_emergence.png content/figures/fig3_alluvial.png
ALL_FIGS := $(MANUSCRIPT_FIGS) \
            content/figures/fig3b_alluvial_core.png \
            content/figures/fig4_genealogy.png content/figures/fig4_seed_axis_core.png \
            content/figures/fig5a_bimodality.png content/figures/figA_1a_robustness.png

figures: $(ALL_FIGS)

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
