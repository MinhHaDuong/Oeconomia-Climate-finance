#!/usr/bin/env bash
# Package data paper for RDJ4HSS submission.
# Follows docs/rdj4hss-author-guidelines.md:
#   - Word file (.docx), default Word styles
#   - Figures as separate files (Figure1.png, etc.)
#   - Tables as separate files (Table1.png)
#   - Acknowledgements as separate file
#   - No embedded illustrations
#
# Usage: bash scripts/package_rdj_submission.sh
# Output: release/2026-03-26 RDJ4HSS/

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$PROJ_ROOT/release/2026-03-26 RDJ4HSS"

echo "=== RDJ4HSS Submission Packager ==="
echo ""

# Clean previous output
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# ── 1. Render .docx via Quarto ──────────────────────────────────────
# Use a temporary _quarto.yml override for docx output with APA-ish settings.
# The main qmd has pdf format; we override to docx here.
echo "[1/6] Rendering data paper to .docx..."

DOCX_QMD="$PROJ_ROOT/content/_data-paper-docx.qmd"

# Create a wrapper qmd that includes the real one but overrides format
cat > "$DOCX_QMD" << 'QMDEOF'
---
format:
  docx:
    reference-doc: default
    number-sections: true
    toc: false
---

{{< include data-paper.qmd >}}
QMDEOF

(cd "$PROJ_ROOT/content" && quarto render _data-paper-docx.qmd --to docx \
    --output "../$OUT_DIR/DataPaper.docx" 2>&1) || {
    echo "ERROR: docx render failed. Trying direct render..."
    # Fallback: render the original qmd directly to docx
    (cd "$PROJ_ROOT/content" && quarto render data-paper.qmd --to docx \
        --output "../$OUT_DIR/DataPaper.docx" 2>&1)
}

# Clean up temporary qmd
rm -f "$DOCX_QMD"

echo "  -> DataPaper.docx"

# ── 2. Copy figure as separate file ─────────────────────────────────
echo "[2/6] Copying figures..."

cp "$PROJ_ROOT/content/figures/fig_bars.png" "$OUT_DIR/Figure1.png"
echo "  -> Figure1.png (annual publication volume)"

# ── 3. Render tables as separate files ──────────────────────────────
# RDJ wants tables as separate illustration files.
# We render the markdown tables to PNG via a minimal HTML+wkhtmltoimage,
# or just provide them as .md + .csv for the journal to typeset.
echo "[3/6] Preparing tables..."

# Table 1: Sources (tbl-sources) — inline in qmd, extract to CSV
cat > "$OUT_DIR/Table1.csv" << 'CSVEOF'
Source,Automation,Coverage
"OpenAlex (Priem et al. 2022)",Automated (free API),"Primary academic source (indexes Crossref, DOAJ, PubMed, and more): tiered keyword search"
ISTEX,Automated (public API),CNRS national text-mining platform (multi-publisher)
Grey literature,Hybrid (curated seed + World Bank API),"16 curated reports (e.g., Buchner 2013) + World Bank repository"
Teaching canon,AI-assisted (scraping + LLM extraction),Syllabus readings from university courses worldwide
bibCNRS,Hand-harvested (CNRS credentials),"CNRS portal aggregating non-English news & discourse (Gale, Wanfang, NewsBank) in FR, ZH, JA, DE"
SciSpace,"AI-collected, hand-exported",SciSpace systematic review tool exports
CSVEOF
echo "  -> Table1.csv (sources)"

# Table 2: Corpus quality (tbl-quality) — generated file
if [ -f "$PROJ_ROOT/content/tables/tab_corpus_sources.csv" ]; then
    cp "$PROJ_ROOT/content/tables/tab_corpus_sources.csv" "$OUT_DIR/Table2.csv"
else
    echo "  WARNING: tab_corpus_sources.csv not found — run 'make corpus-tables' first"
fi
echo "  -> Table2.csv (corpus quality)"

# Table 3: Languages (tbl-languages) — generated markdown, copy as-is
if [ -f "$PROJ_ROOT/content/tables/tab_languages.md" ]; then
    cp "$PROJ_ROOT/content/tables/tab_languages.md" "$OUT_DIR/Table3.md"
else
    echo "  WARNING: tab_languages.md not found — run 'make corpus-tables' first"
fi
echo "  -> Table3.md (languages)"

# ── 4. Acknowledgements as separate file ────────────────────────────
echo "[4/6] Creating acknowledgements file..."

cat > "$OUT_DIR/Acknowledgements.txt" << 'ACKEOF'
Acknowledgements

This work was supported by CNRS (Centre National de la Recherche Scientifique) through the
author's permanent research position at CIRED (Centre International de Recherche sur
l'Environnement et le Développement).

AI disclosure: Claude (Anthropic) assisted with extracting bibliographic references from
university course syllabi for the teaching canon component. All extracted references were
validated against Crossref metadata. The AI had no role in corpus design, quality filtering,
analysis, or manuscript writing.
ACKEOF
echo "  -> Acknowledgements.txt"

# ── 5. Cover letter ─────────────────────────────────────────────────
echo "[5/6] Copying cover letter..."

if [ -f "$PROJ_ROOT/release/cover-letter-rdj.txt" ]; then
    cp "$PROJ_ROOT/release/cover-letter-rdj.txt" "$OUT_DIR/CoverLetter.txt"
    echo "  -> CoverLetter.txt"
else
    echo "  WARNING: cover-letter-rdj.txt not found"
fi

# ── 6. Word count check ────────────────────────────────────────────
echo "[6/6] Word count check..."

if command -v pdftotext &>/dev/null && [ -f "$PROJ_ROOT/output/content/data-paper.pdf" ]; then
    TOTAL=$(pdftotext "$PROJ_ROOT/output/content/data-paper.pdf" - 2>/dev/null | wc -w)
    # Body only: between "1. Introduction" and "Data and Code Availability"
    BODY=$(pdftotext "$PROJ_ROOT/output/content/data-paper.pdf" - 2>/dev/null \
        | sed -n '/^1[. ]*Introduction/,/^Data and Code Availability/p' | wc -w)
    echo "  Total words (PDF):  $TOTAL"
    echo "  Body words (§1–4):  $BODY"
    if [ "$BODY" -gt 2500 ]; then
        echo "  *** WARNING: Body exceeds 2,500-word limit by $((BODY - 2500)) words ***"
    else
        echo "  OK: within 2,500-word limit"
    fi
else
    echo "  (skipped — pdftotext or PDF not available)"
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "=== Submission package ready ==="
echo "Directory: $OUT_DIR"
echo ""
ls -la "$OUT_DIR"
echo ""
echo "Checklist before submission:"
echo "  [ ] Word count <= 2,500"
echo "  [ ] Open DataPaper.docx — verify tables render, cross-refs resolved"
echo "  [ ] Verify APA 7th citation format in docx"
echo "  [ ] Keywords are lowercase"
echo "  [ ] Zenodo deposit published (DOI: 10.5281/zenodo.19236130)"
echo "  [ ] Upload to https://platform.openjournals.nl/RDJHSS"
