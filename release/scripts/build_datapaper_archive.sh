#!/usr/bin/env bash
# Build the data paper reproducibility archive for Zenodo.
#
# Produces climate-finance-datapaper.tar.gz containing:
#   code/  — full pipeline source (git archive) + pre-built figures/tables
#   data/  — deposit files (corpus CSV without abstracts, embeddings, citations, catalogs)
#
# Prerequisites: make check-corpus corpus-tables figures-datapaper
# Usage: bash release/scripts/build_datapaper_archive.sh

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ARCHIVE=climate-finance-datapaper
TMP="/tmp/$ARCHIVE"
DATA_DIR="$PROJ_ROOT/data/catalogs"

echo "=== Building data paper archive ==="

rm -rf "$TMP"
mkdir -p "$TMP/code" "$TMP/data"

# ── Code: pipeline source via git archive ────────────────
echo "  Extracting code from git..."
git -C "$PROJ_ROOT" archive HEAD | tar -x -C "$TMP/code"
rm -rf "$TMP/code/.dvc" "$TMP/code/attic" "$TMP/code/.claude"

# ── Data: deposit files ──────────────────────────────────
echo "  Preparing deposit CSV (dropping abstracts)..."
cd "$PROJ_ROOT"
uv run python scripts/prepare_deposit.py --out-dir "$TMP/data"

echo "  Copying embeddings, citations, and source catalogs..."
cp -L "$DATA_DIR/embeddings.npz" "$TMP/data/"
cp -L "$DATA_DIR/citations.csv" "$TMP/data/"
for src in openalex istex bibcnrs scispace grey teaching; do
    cp -L "$DATA_DIR/${src}_works.csv" "$TMP/data/" 2>/dev/null || true
done

# ── Quarto project config: data paper only ───────────────
# The repo _quarto.yml lists all papers; Quarto scans them all even when
# rendering one file. Replace with a minimal config for the data paper.
cat > "$TMP/code/_quarto.yml" << 'YAML'
project:
  type: default
  output-dir: output
  render:
    - content/data-paper.qmd

bibliography: content/bibliography/main.bib

format:
  pdf:
    pdf-engine: xelatex
    cite-method: citeproc
YAML

# ── Figures, tables, vars for rendering (hard fail) ──────
echo "  Copying figures and tables..."
mkdir -p "$TMP/code/content/figures" "$TMP/code/content/tables"
cp content/figures/fig_bars.png "$TMP/code/content/figures/"
cp content/tables/tab_corpus_sources.md content/tables/tab_languages.md \
   "$TMP/code/content/tables/"
cp content/data-paper-vars.yml "$TMP/code/content/"

# ── Checksums for make verify ────────────────────────────
echo "  Computing data checksums..."
cd "$TMP/data" && md5sum * > "$TMP/code/checksums-data.md5"

# ── Tarball ──────────────────────────────────────────────
echo "=== Creating tarball ==="
tar czf "$PROJ_ROOT/$ARCHIVE.tar.gz" -C /tmp \
    --exclude='__pycache__' --exclude='.venv' \
    "$ARCHIVE"

echo "=== Data paper archive ==="
du -h "$PROJ_ROOT/$ARCHIVE.tar.gz"
echo "Files: $(tar tzf "$PROJ_ROOT/$ARCHIVE.tar.gz" | wc -l)"
rm -rf "$TMP"
echo "Done: $ARCHIVE.tar.gz"
