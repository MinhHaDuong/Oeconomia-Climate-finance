# mk/archives.mk — Reproducibility archives
#
# Three archive types:
#   archive-analysis     Data + scripts: reviewers verify figures/tables
#   archive-manuscript   Pre-built figures + content: reviewers verify PDF renders
#   archive-datapaper    Complete pipeline: reviewers verify with dvc repro

SHELL            := /bin/bash
ANALYSIS_ARCHIVE := climate-finance-analysis
ANALYSIS_TMP     := /tmp/$(ANALYSIS_ARCHIVE)
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
	cp scripts/pipeline_loaders.py          $(ANALYSIS_TMP)/scripts/
	cp scripts/pipeline_io.py               $(ANALYSIS_TMP)/scripts/
	cp scripts/pipeline_progress.py         $(ANALYSIS_TMP)/scripts/
	cp scripts/pipeline_text.py             $(ANALYSIS_TMP)/scripts/
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
	cp scripts/compute_clusters.py          $(ANALYSIS_TMP)/scripts/
	@# Config + build infrastructure
	cp config/analysis.yaml             $(ANALYSIS_TMP)/config/
	cp config/v1_tab_alluvial.csv       $(ANALYSIS_TMP)/config/
	cp config/v1_cluster_labels.json    $(ANALYSIS_TMP)/config/
	cp config/v1_cluster_centroids.npy  $(ANALYSIS_TMP)/config/
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
	cp content/figures/fig_bars_v1.png      $(MANU_TMP)/content/figures/
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
archive-datapaper: check-corpus corpus-tables figures-datapaper
	bash scripts/build_datapaper_archive.sh
