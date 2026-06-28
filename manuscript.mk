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
# NOTE: content/manuscript-Gide.qmd is the author's working draft and is
# deliberately NOT git-tracked yet, so `make gide` builds only where that file
# is present (the author's checkout), not in a clean-room checkout. Track it
# later to make this workpackage fully reproducible (cf. the manuscript slice of
# ticket 0131).
GIDE_SRC     := content/manuscript-Gide.qmd
GIDE_PROFILE := _quarto-manuscript-Gide.yml

GIDE_INPUTS := $(GIDE_SRC) $(MANUSCRIPT_BIB) $(MANUSCRIPT_CSL) \
               $(MANUSCRIPT_VARS) $(GIDE_PROFILE) $(MANUSCRIPT_DELIVERABLES)

output/content/manuscript-Gide.pdf: export QUARTO_PROFILE := manuscript-Gide

output/content/manuscript-Gide.pdf: $(GIDE_INPUTS)
	quarto render $(GIDE_SRC) --to pdf

.PHONY: gide
gide: output/content/manuscript-Gide.pdf
