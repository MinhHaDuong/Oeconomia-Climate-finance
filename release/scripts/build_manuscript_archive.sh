#!/usr/bin/env bash
# Build the manuscript reproducibility archive (Phase 3).
# Extracted from Makefile archive-manuscript recipe.
#
# Produces climate-finance-manuscript.tar.gz containing:
#   content/  — manuscript source, figures, tables, bibliography
#   expected-manuscript.pdf — pre-built reference PDF
#
# Prerequisites: figures, includes, manuscript-vars.yml, and PDF built
# No Python needed — only Quarto + XeLaTeX.
# Usage: bash release/scripts/build_manuscript_archive.sh

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ARCHIVE=climate-finance-manuscript
TMP="/tmp/$ARCHIVE"

echo "=== Building manuscript archive ==="

rm -rf "$TMP"
mkdir -p "$TMP/content/bibliography" \
         "$TMP/content/tables" \
         "$TMP/content/figures"

cd "$PROJ_ROOT"

# Pre-built figures (validated, not regenerated)
cp content/figures/fig_bars_v1.png     "$TMP/content/figures/"
cp content/figures/fig_composition.png "$TMP/content/figures/"

# Manuscript content
cp content/manuscript.qmd          "$TMP/content/"
cp content/manuscript-vars.yml     "$TMP/content/"
cp content/author-footnote.tex     "$TMP/content/"
cp content/tables/tab_venues.md    "$TMP/content/tables/"
cp content/bibliography/main.bib   "$TMP/content/bibliography/"
cp content/bibliography/oeconomia.csl "$TMP/content/bibliography/"

# Pre-built output PDF (at root, away from Quarto's clean scope)
cp output/content/manuscript.pdf   "$TMP/expected-manuscript.pdf"

# Build infrastructure (no Python needed)
cp release/templates/Makefile.manuscript "$TMP/Makefile"
cp _quarto.yml                     "$TMP/"

# README for reviewers
cp release/templates/README-manuscript.md "$TMP/README.md"

# Record toolchain versions used to build the shipped PDF
printf 'Quarto %s\n%s\n' "$(quarto --version)" "$(xdvipdfmx --version 2>&1 | head -1)" > "$TMP/TOOLCHAIN.txt"

# Input checksums — reviewers verify with: make && make verify
cd "$TMP" && md5sum content/figures/*.png content/tables/*.md \
    content/bibliography/main.bib content/manuscript.qmd \
    content/manuscript-vars.yml > checksums.md5

# Tarball
echo "=== Creating tarball ==="
tar czf "$PROJ_ROOT/$ARCHIVE.tar.gz" -C /tmp "$ARCHIVE"
echo "=== Manuscript archive ==="
du -h "$PROJ_ROOT/$ARCHIVE.tar.gz"
echo "Files: $(tar tzf "$PROJ_ROOT/$ARCHIVE.tar.gz" | wc -l)"
rm -rf "$TMP"
echo "Done: $ARCHIVE.tar.gz"
