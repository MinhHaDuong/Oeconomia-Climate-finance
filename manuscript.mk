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
