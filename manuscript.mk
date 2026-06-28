# manuscript.mk — Phase 3 writing workpackage for the Œconomia article.
#
# Standalone clean-room build: produces output/content/manuscript.{pdf,docx}
# from committed handoff artifacts ALONE — no uv, no Python, no corpus data.
# Toolchain: Quarto + a LaTeX engine (XeLaTeX via TeX Live) + Pandoc only.
#
#   make -f manuscript.mk output/content/manuscript.pdf
#
# Also -include'd by the top-level Makefile so `make manuscript` resolves the
# same rules. Prerequisites are the prose source plus the git-tracked writing
# deliverables (3 figures + tab_venues.md, see .gitignore negations) and the
# committed bibliography/vars — every one present in a fresh checkout. The
# Phase-2 figure-from-data rules that PRODUCE these deliverables stay in the
# main Makefile; this file only CONSUMES them. (Ticket 0131.)

# Reproducible PDF metadata timestamps when built standalone (the top-level
# Makefile exports the same; ?=-style guard keeps it a no-op when included).
export SOURCE_DATE_EPOCH ?= 0

# Quarto walks EVERY doc in _quarto.yml's render list during project discovery,
# even when one file is targeted — so a bare `quarto render manuscript.qmd`
# fails on the sibling papers' includes (tab_corpus_sources.md, tab_languages.md,
# tab_citation_coverage.md), which are other workpackages' deliverables and are
# deliberately absent here. The `manuscript` Quarto profile (_quarto-manuscript.yml)
# excludes those siblings from discovery, isolating the manuscript build. Set
# per-target (not file-scope) so it does NOT leak into `make papers` when this
# file is -include'd by the top-level Makefile.

# Writing-facing manuscript deliverables — git-tracked, byte-stable.
MANUSCRIPT_SRC      := content/manuscript.qmd
MANUSCRIPT_BIB      := content/bibliography/main.bib
MANUSCRIPT_CSL      := content/bibliography/oeconomia.csl
MANUSCRIPT_VARS     := content/manuscript-vars.yml
MANUSCRIPT_DELIVERABLES := content/figures/fig_bars_v1.png \
                           content/figures/fig_composition.png \
                           content/figures/fig_breaks.png \
                           content/tables/tab_venues.md

MANUSCRIPT_PROFILE  := _quarto-manuscript.yml

MANUSCRIPT_INPUTS := $(MANUSCRIPT_SRC) $(MANUSCRIPT_BIB) $(MANUSCRIPT_CSL) \
                     $(MANUSCRIPT_VARS) $(MANUSCRIPT_PROFILE) \
                     $(MANUSCRIPT_DELIVERABLES)

output/content/manuscript.pdf output/content/manuscript.docx: export QUARTO_PROFILE := manuscript

output/content/manuscript.pdf: $(MANUSCRIPT_INPUTS)
	quarto render $(MANUSCRIPT_SRC) --to pdf

output/content/manuscript.docx: $(MANUSCRIPT_INPUTS)
	quarto render $(MANUSCRIPT_SRC) --to docx

# ── Charles Gide conference variant ─────────────────────────────────────────
# Short French paper (manuscript-Gide.qmd) presented at the 21e colloque Charles
# Gide. Same writing workpackage: shares the manuscript's git-tracked figures +
# tab_venues.md and manuscript-vars.yml. Its own Quarto profile excludes ALL
# sibling docs (including manuscript.qmd) so a bare render builds only the Gide
# paper. No data, no uv — Quarto + LaTeX only.
#
# content/manuscript-Gide.qmd is git-tracked. The figures and tables it consumes
# are tracked handoff artifacts too; regenerating them from data is the analysis
# workpackage's job, so render this paper with those artifacts already present
# (a full data-less clean-room rebuild is tracked in ticket 0131).
GIDE_SRC        := content/manuscript-Gide.qmd
GIDE_PROFILE    := _quarto-manuscript-Gide.yml
# French-caption variant of the shared venues table: identical English table body
# (headers, journal names, counts) with a French caption. Derived from the
# git-tracked tab_venues.md, so it stays in sync when that table is regenerated.
# Writing-side only: a plain-text transform, no uv and no data.
GIDE_VENUES_FR  := content/tables/tab_venues_fr.md

$(GIDE_VENUES_FR): content/tables/tab_venues.md content/tables/tab_venues_fr_caption.md
	{ grep -v '^: ' $< ; cat content/tables/tab_venues_fr_caption.md ; } > $@

GIDE_INPUTS := $(GIDE_SRC) $(MANUSCRIPT_BIB) $(MANUSCRIPT_CSL) \
               $(MANUSCRIPT_VARS) $(GIDE_PROFILE) \
               $(MANUSCRIPT_DELIVERABLES) $(GIDE_VENUES_FR)

output/content/manuscript-Gide.pdf: export QUARTO_PROFILE := manuscript-Gide

output/content/manuscript-Gide.pdf: $(GIDE_INPUTS)
	quarto render $(GIDE_SRC) --to pdf

.PHONY: gide
gide: output/content/manuscript-Gide.pdf
