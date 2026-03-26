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
.PHONY: all setup manuscript papers figures figures-manuscript figures-datapaper figures-companion figures-techrep stats check check-fast check-corpus check-manuscript-data corpus corpus-sync corpus-discover corpus-enrich corpus-extend corpus-filter corpus-align corpus-filter-all corpus-tables corpus-validate deploy-corpus lint-prose clean rebuild archive-analysis archive-manuscript archive-datapaper

.DEFAULT_GOAL := manuscript

all: manuscript papers

# ── Include modules ──────────────────────────────────────
# Phase 2 (figures, tables, stats), Phase 3 (render), archives
include mk/figures.mk
include mk/render.mk
include mk/archives.mk

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
	@[ "$$(hostname)" = "padme" ] || { echo "error: make corpus runs on padme only. Use 'make corpus-sync' on $$(hostname)."; exit 1; }
	@uv run dvc version >/dev/null 2>&1 || { echo "error: dvc not found. Install with: uv tool install 'dvc[ssh]'"; exit 1; }
	@[ "$$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "error: make corpus must run on main (currently on $$(git rev-parse --abbrev-ref HEAD))."; exit 1; }
	uv run dvc repro; ret=$$?; uv run dvc push; \
	if [ $$ret -ne 0 ]; then exit $$ret; fi; \
	changed=$$(git status --porcelain); \
	if [ -z "$$changed" ]; then \
		echo "dvc.lock unchanged, nothing to commit."; \
	elif [ "$$(echo "$$changed" | sed 's/^...//')" = "dvc.lock" ]; then \
		echo "Auto-committing dvc.lock..."; \
		branch="housekeeping-dvclock-$$(date +%Y%m%d-%H%M%S)"; \
		git checkout -b "$$branch" && \
		git add dvc.lock && \
		git commit -m "data: update dvc.lock after pipeline re-run" && \
		git checkout main && \
		git merge "$$branch" && \
		git branch -d "$$branch" && \
		git push origin main && \
		echo "dvc.lock committed and pushed."; \
	else \
		echo ""; echo "WARNING: files other than dvc.lock changed:"; echo "$$changed"; \
		echo "Stage and commit manually."; \
	fi

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

# ── All checks (tests + lint) ────────────────────────────
check: lint-prose
	uv run pytest tests/ -v --tb=short

# Fast subset: unit tests only (no Python subprocess spawning, no sleeps, < 20s).
check-fast: lint-prose
	uv run pytest tests/ -v --tb=short -m "not slow and not integration"

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
