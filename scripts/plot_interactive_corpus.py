"""Interactive HTML exploration of the core climate finance corpus.

Produces a standalone Plotly scatter plot of the ~1,176 core papers
(cited_by_count >= 50) with:
  - X-axis: year (with jitter to reduce overplotting)
  - Y-axis: seed axis score (efficiency <-> accountability spectrum)
  - Color: KMeans semantic cluster (6 clusters)
  - Hover: title, first_author, year, journal, cited_by_count
  - Click: opens DOI link in new tab
  - Highlighted: papers cited in bibliography/main.bib (star markers)
  - ISTEX papers: PDF link in tooltip

Output: figures/interactive_core_corpus.html

Usage:
    uv run python scripts/plot_interactive_corpus.py [--no-pdf]
"""

import argparse
import json
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi

# --- Args ---
parser = argparse.ArgumentParser(
    description="Interactive HTML scatter of core corpus (Fig interactive)"
)
parser.add_argument("--no-pdf", action="store_true",
                    help="(no effect — kept for interface consistency)")
args = parser.parse_args()

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")
CLUSTERS_PATH = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")
CLUSTER_LABELS_PATH = os.path.join(CATALOGS_DIR, "cluster_labels.json")
BIB_PATH = os.path.join(BASE_DIR, "bibliography", "main.bib")

# Tab5 can be in tables/ (repo) or catalogs/ (data dir) — try both
TAB5_CANDIDATES = [
    os.path.join(TABLES_DIR, "tab_pole_papers.csv"),
    os.path.join(CATALOGS_DIR, "tab_pole_papers.csv"),
]

CITE_THRESHOLD = 50
JITTER_HALF = 0.3  # +/- years for x-axis jitter

# Qualitative color palette (Plotly's Set2-like)
CLUSTER_COLORS = [
    "#66c2a5",  # teal
    "#fc8d62",  # orange
    "#8da0cb",  # blue-violet
    "#e78ac3",  # pink
    "#a6d854",  # lime
    "#ffd92f",  # yellow
]


# ── 1. Load refined works ──────────────────────────────────────────────
print("Loading refined_works.csv ...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce")

# Normalize DOIs for joining
works["doi_norm"] = works["doi"].apply(normalize_doi)


# ── 2. Load axis scores (tab_pole_papers.csv) ────────────────────────
tab5_path = None
for candidate in TAB5_CANDIDATES:
    if os.path.exists(candidate):
        tab5_path = candidate
        break

if tab5_path is None:
    raise FileNotFoundError(
        "tab_pole_papers.csv not found in tables/ or catalogs/. "
        "Run analyze_bimodality.py first."
    )

print(f"Loading axis scores from {tab5_path} ...")
tab5 = pd.read_csv(tab5_path)
tab5["doi_norm"] = tab5["doi"].apply(normalize_doi)

# Join axis_score onto works via normalized DOI
works = works.merge(
    tab5[["doi_norm", "axis_score"]].drop_duplicates(subset="doi_norm"),
    on="doi_norm",
    how="left",
)
n_with_score = works["axis_score"].notna().sum()
print(f"  Axis scores joined: {n_with_score:,} / {len(works):,}")


# ── 3. Load semantic clusters ─────────────────────────────────────────
print("Loading semantic clusters ...")
clusters = pd.read_csv(CLUSTERS_PATH)
clusters["doi_norm"] = clusters["doi"].apply(normalize_doi)

# Join cluster onto works via normalized DOI
works = works.merge(
    clusters[["doi_norm", "semantic_cluster"]].drop_duplicates(subset="doi_norm"),
    on="doi_norm",
    how="left",
)
n_clustered = works["semantic_cluster"].notna().sum()
print(f"  Clusters joined: {n_clustered:,} / {len(works):,}")

# Load cluster labels
cluster_labels = {}
if os.path.exists(CLUSTER_LABELS_PATH):
    with open(CLUSTER_LABELS_PATH) as f:
        cluster_labels = json.load(f)
    print(f"  Loaded {len(cluster_labels)} cluster labels")


# ── 4. Filter to core papers with axis scores ─────────────────────────
core = works[
    (works["cited_by_count"] >= CITE_THRESHOLD)
    & works["axis_score"].notna()
    & works["year"].notna()
].copy()
print(f"Core papers with axis scores: {len(core):,}")


# ── 5. Parse bibliography DOIs for highlighting ───────────────────────
print("Parsing bibliography DOIs ...")
bib_dois = set()

# Use bibtexparser if available, fall back to regex
try:
    import bibtexparser
    with open(BIB_PATH) as f:
        bib = bibtexparser.load(f)
    for entry in bib.entries:
        doi = entry.get("doi", "")
        if doi:
            bib_dois.add(normalize_doi(doi))
    print(f"  bibtexparser: {len(bib_dois)} DOIs from {len(bib.entries)} entries")
except ImportError:
    # Fallback: regex extraction
    with open(BIB_PATH) as f:
        bib_text = f.read()
    for m in re.finditer(r'doi\s*=\s*\{([^}]+)\}', bib_text, re.IGNORECASE):
        bib_dois.add(normalize_doi(m.group(1)))
    print(f"  regex fallback: {len(bib_dois)} DOIs extracted")

# Mark cited-in-manuscript papers
core["in_bib"] = core["doi_norm"].isin(bib_dois)
n_bib = core["in_bib"].sum()
print(f"  Core papers cited in manuscript: {n_bib}")


# ── 6. Identify ISTEX papers ──────────────────────────────────────────
core["is_istex"] = core["source"].str.contains("istex", case=False, na=False)

# Build ISTEX PDF link: for pure ISTEX papers, source_id is the hash
# For openalex|istex, source_id is an OpenAlex W-ID (no ISTEX link available)
def make_istex_url(row):
    """Build ISTEX fulltext PDF URL when possible."""
    if not row["is_istex"]:
        return ""
    sid = str(row.get("source_id", ""))
    # Pure ISTEX papers have a 40-char hex hash as source_id
    if re.match(r'^[A-Fa-f0-9]{40}$', sid):
        return f"https://api.istex.fr/document/{sid}/fulltext/pdf"
    return ""

core["istex_url"] = core.apply(make_istex_url, axis=1)
n_istex = (core["istex_url"] != "").sum()
print(f"  Core ISTEX papers with PDF link: {n_istex}")


# ── 7. Prepare plot data ──────────────────────────────────────────────
rng = np.random.default_rng(42)
core["year_jitter"] = core["year"].values + rng.uniform(
    -JITTER_HALF, JITTER_HALF, size=len(core)
)

# Cluster as integer, fill NaN with -1 for "unassigned"
core["cluster"] = core["semantic_cluster"].fillna(-1).astype(int)

# Build DOI URLs
core["doi_url"] = core["doi_norm"].apply(
    lambda d: f"https://doi.org/{d}" if d else ""
)

# Shorten title for display (cap at 100 chars)
core["title_short"] = core["title"].fillna("").apply(
    lambda t: (t[:97] + "...") if len(t) > 100 else t
)

# Journal short (cap at 60 chars)
core["journal_short"] = core["journal"].fillna("").apply(
    lambda j: (j[:57] + "...") if len(j) > 60 else j
)


# ── 8. Build Plotly figure ─────────────────────────────────────────────
print("Building interactive figure ...")

fig = go.Figure()

# Split data: non-bib by cluster, then bib papers on top
cluster_ids = sorted(core["cluster"].unique())
cluster_ids = [c for c in cluster_ids if c >= 0]  # valid clusters first

# --- Non-bib traces (one per cluster, circle markers) ---
non_bib = core[~core["in_bib"]]
for cid in cluster_ids:
    mask = non_bib["cluster"] == cid
    subset = non_bib[mask]
    if len(subset) == 0:
        continue

    label = cluster_labels.get(str(cid), f"Cluster {cid}")
    color = CLUSTER_COLORS[cid % len(CLUSTER_COLORS)]

    # Build custom hover text
    hover_texts = []
    for _, row in subset.iterrows():
        lines = [
            f"<b>{row['title_short']}</b>",
            f"{row['first_author']} ({int(row['year'])})",
            f"{row['journal_short']}",
            f"Cited by: {int(row['cited_by_count'])}",
        ]
        if row["istex_url"]:
            lines.append(f"ISTEX PDF: {row['istex_url']}")
        hover_texts.append("<br>".join(lines))

    fig.add_trace(go.Scatter(
        x=subset["year_jitter"],
        y=subset["axis_score"],
        mode="markers",
        marker=dict(
            size=6,
            color=color,
            opacity=0.6,
            line=dict(width=0.5, color="white"),
        ),
        name=f"C{cid}: {label}",
        text=hover_texts,
        hoverinfo="text",
        customdata=subset["doi_url"].values,
        legendgroup=f"cluster_{cid}",
    ))

# Handle unassigned cluster (-1) if any
unassigned = non_bib[non_bib["cluster"] == -1]
if len(unassigned) > 0:
    hover_texts = []
    for _, row in unassigned.iterrows():
        lines = [
            f"<b>{row['title_short']}</b>",
            f"{row['first_author']} ({int(row['year'])})",
            f"{row['journal_short']}",
            f"Cited by: {int(row['cited_by_count'])}",
        ]
        hover_texts.append("<br>".join(lines))

    fig.add_trace(go.Scatter(
        x=unassigned["year_jitter"],
        y=unassigned["axis_score"],
        mode="markers",
        marker=dict(size=5, color="#999999", opacity=0.4),
        name="Unassigned",
        text=hover_texts,
        hoverinfo="text",
        customdata=unassigned["doi_url"].values,
        legendgroup="unassigned",
    ))

# --- Bib-cited traces (star markers, one per cluster, on top) ---
bib_papers = core[core["in_bib"]]
if len(bib_papers) > 0:
    for cid in cluster_ids:
        mask = bib_papers["cluster"] == cid
        subset = bib_papers[mask]
        if len(subset) == 0:
            continue

        color = CLUSTER_COLORS[cid % len(CLUSTER_COLORS)]

        hover_texts = []
        for _, row in subset.iterrows():
            lines = [
                f"<b>{row['title_short']}</b>",
                f"{row['first_author']} ({int(row['year'])})",
                f"{row['journal_short']}",
                f"Cited by: {int(row['cited_by_count'])}",
                "<i>Cited in manuscript</i>",
            ]
            if row["istex_url"]:
                lines.append(f"ISTEX PDF: {row['istex_url']}")
            hover_texts.append("<br>".join(lines))

        # Show legend only for first bib cluster trace
        show_legend = bool(cid == min(
            bib_papers[bib_papers["cluster"].isin(cluster_ids)]["cluster"]
        ))

        fig.add_trace(go.Scatter(
            x=subset["year_jitter"],
            y=subset["axis_score"],
            mode="markers",
            marker=dict(
                size=12,
                color=color,
                symbol="star",
                opacity=0.9,
                line=dict(width=1, color="black"),
            ),
            name="Cited in manuscript" if show_legend else "",
            showlegend=show_legend,
            text=hover_texts,
            hoverinfo="text",
            customdata=subset["doi_url"].values,
            legendgroup="bib_cited",
        ))


# ── 9. Layout and click-to-DOI JavaScript ─────────────────────────────

# Period boundaries as vertical lines
period_breaks = [2007, 2015]
for yr in period_breaks:
    fig.add_vline(
        x=yr - 0.5, line_dash="dash", line_color="grey", opacity=0.5,
        annotation_text=str(yr), annotation_position="top",
    )

# Period labels
period_labels = [
    ("Before climate finance", 1998, 0),
    ("Crystallization", 2010.5, 0),
    ("Established field", 2020, 0),
]

fig.update_layout(
    title=dict(
        text="Core Climate Finance Scholarship (cited \u2265 50)",
        font=dict(size=18),
    ),
    xaxis=dict(
        title="Year",
        dtick=5,
        range=[1989, 2026.5],
    ),
    yaxis=dict(
        title="\u2190 Accountability  |  Efficiency \u2192",
        zeroline=True,
        zerolinecolor="lightgrey",
        zerolinewidth=1,
    ),
    legend=dict(
        title="Semantic clusters",
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="lightgrey",
        borderwidth=1,
        font=dict(size=11),
    ),
    hovermode="closest",
    template="plotly_white",
    width=1100,
    height=650,
    margin=dict(l=80, r=30, t=60, b=60),
)

# Add period labels as annotations
for label_text, x_pos, y_pos in period_labels:
    fig.add_annotation(
        x=x_pos,
        y=1.06,
        yref="paper",
        text=label_text,
        showarrow=False,
        font=dict(size=11, color="grey"),
    )

# Add a zero-line annotation
fig.add_annotation(
    x=0.01, xref="paper",
    y=0, yref="y",
    text="neutral",
    showarrow=False,
    font=dict(size=9, color="grey"),
    xanchor="left",
)


# ── 10. Write HTML with click-to-DOI ──────────────────────────────────
output_path = os.path.join(FIGURES_DIR, "interactive_core_corpus.html")

# Generate the base HTML
html_str = fig.to_html(
    include_plotlyjs="cdn",
    full_html=True,
    config={
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "displaylogo": False,
    },
)

# Inject click handler JavaScript: open DOI in new tab on point click
click_js = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    var plotDiv = document.getElementsByClassName('plotly-graph-div')[0];
    if (plotDiv) {
        plotDiv.on('plotly_click', function(data) {
            if (data.points && data.points.length > 0) {
                var url = data.points[0].customdata;
                if (url && url.length > 0) {
                    window.open(url, '_blank');
                }
            }
        });
    }
});
</script>
"""

# Insert before closing </body> tag
html_str = html_str.replace("</body>", click_js + "</body>")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_str)

file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
print(f"\nSaved: {output_path}")
print(f"  File size: {file_size_mb:.2f} MB")
print(f"  Core papers plotted: {len(core):,}")
print(f"  Bib-highlighted: {n_bib}")
print(f"  Clusters: {len(cluster_ids)}")
print("Done.")
