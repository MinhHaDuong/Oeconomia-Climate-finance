#!/usr/bin/env bash
# Build the analysis reproducibility archive (Phase 2).
# Extracted from Makefile archive-analysis recipe.
#
# Produces climate-finance-analysis.tar.gz containing:
#   data/     — Phase 1 contract data (refined_works, embeddings)
#   scripts/  — analysis scripts that produce figures + tables
#   config/   — analysis parameters and frozen v1 data
#
# Prerequisites: make check-manuscript-data + all ANALYSIS_OUTPUTS built
# Usage: bash release/scripts/build_analysis_archive.sh

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA_DIR="$PROJ_ROOT/data/catalogs"
ARCHIVE=climate-finance-analysis
TMP="/tmp/$ARCHIVE"

# Analysis outputs — must match Makefile ANALYSIS_OUTPUTS
ANALYSIS_OUTPUTS=(
    content/figures/fig_bars_v1.png
    content/figures/fig_composition.png
    content/tables/tab_venues.md
    content/tables/tab_alluvial.csv
    content/tables/tab_core_shares.csv
    content/tables/tab_bimodality.csv
    content/tables/tab_axis_detection.csv
    content/tables/tab_pole_papers.csv
    content/tables/cluster_labels.json
)

echo "=== Building analysis archive ==="

rm -rf "$TMP"
mkdir -p "$TMP/data/catalogs" \
         "$TMP/scripts" \
         "$TMP/config" \
         "$TMP/content/figures" \
         "$TMP/content/tables"

cd "$PROJ_ROOT"

# Phase 1 contract data (dereference DVC symlinks)
cp -L "$DATA_DIR/refined_works.csv"     "$TMP/data/catalogs/"
cp -L "$DATA_DIR/refined_embeddings.npz" "$TMP/data/catalogs/"

# Scripts needed to build figures + tables
for s in utils.py pipeline_loaders.py pipeline_io.py pipeline_progress.py \
         pipeline_text.py plot_style.py plot_fig1_bars.py \
         plot_fig2_composition.py compute_clusters.py build_het_core.py \
         export_core_venues_markdown.py summarize_core_venues.py \
         export_tab_venues.py export_citation_coverage.py analyze_bimodality.py; do
    cp "scripts/$s" "$TMP/scripts/"
done

# Config + build infrastructure
cp config/analysis.yaml            "$TMP/config/"
cp config/v1_tab_alluvial.csv      "$TMP/config/"
cp config/v1_cluster_labels.json   "$TMP/config/"
cp config/v1_cluster_centroids.npy "$TMP/config/"
cp release/templates/Makefile.analysis-manuscript "$TMP/Makefile"
cp pyproject.toml uv.lock          "$TMP/"
echo 'CLIMATE_FINANCE_DATA=data' > "$TMP/.env"

# README + container file for reviewers
cp release/templates/README-analysis.md  "$TMP/README.md"
cp release/templates/Dockerfile.analysis "$TMP/Dockerfile"

# Expected output checksums — reviewers verify with: make && make verify
cd "$PROJ_ROOT"
md5sum "${ANALYSIS_OUTPUTS[@]}" > "$TMP/expected_outputs.md5"

# Tarball
echo "=== Creating tarball ==="
tar czf "$PROJ_ROOT/$ARCHIVE.tar.gz" -C /tmp "$ARCHIVE"
echo "=== Analysis archive ==="
du -h "$PROJ_ROOT/$ARCHIVE.tar.gz"
echo "Files: $(tar tzf "$PROJ_ROOT/$ARCHIVE.tar.gz" | wc -l)"
rm -rf "$TMP"
echo "Done: $ARCHIVE.tar.gz"
