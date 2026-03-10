"""Time-ordered citation genealogy of intellectual communities.

Visualizes the citation DAG constrained by community structure, with papers
positioned by year (x-axis) and lineage band (y-axis).

Produces:
- figures/fig_genealogy.pdf: Citation genealogy (~500+ papers)
- tables/tab_lineages.csv: Lineage assignments for backbone papers

Options:
  --robustness        Louvain resolution sensitivity (R3)
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from matplotlib.path import Path

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi, save_figure

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

# COP events
COP_EVENTS = {
    1992: "Rio",
    1997: "Kyoto",
    2009: "Copenhagen",
    2015: "Paris",
    2021: "Glasgow",
    2024: "Baku",
}

# Periods (three-act structure from breakpoint detection)
PERIOD_BOUNDS = [1990, 2007, 2015, 2026]
PERIOD_LABELS = ["1990–2006", "2007–2014", "2015–2025"]
PERIOD_COLORS = ["#f0f0f0", "#e8e8e8", "#f0f0f0", "#e8e8e8"]

# --- Args ---
parser = argparse.ArgumentParser(description="Citation genealogy figure")
parser.add_argument("--robustness", action="store_true",
                    help="Run Louvain resolution sensitivity (R3)")
parser.add_argument("--no-pdf", action="store_true",
                    help="Skip PDF generation (PNG only)")
args = parser.parse_args()


# ============================================================
# Step 1: Load data
# ============================================================

print("Loading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)

# Build DOI → metadata lookup
doi_meta = {}
for _, row in works.iterrows():
    d = row["doi_norm"]
    if d and d not in ("", "nan", "none"):
        doi_meta[d] = {
            "title": str(row.get("title", "") or ""),
            "first_author": str(row.get("first_author", "") or ""),
            "year": row["year"] if pd.notna(row["year"]) else None,
            "cited_by_count": row["cited_by_count"],
            "abstract": str(row.get("abstract", "") or ""),
        }

# Load citations
print("Loading citations...")
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none"])]
cit = cit[~cit["ref_doi"].isin(["nan", "none"])]

# Also add ref metadata from citations (for papers not in unified_works)
for _, row in cit.iterrows():
    d = row["ref_doi"]
    if d and d not in ("", "nan", "none") and d not in doi_meta:
        yr = row.get("ref_year", None)
        if pd.notna(yr):
            try:
                yr = float(yr)
            except (ValueError, TypeError):
                yr = None
        else:
            yr = None
        doi_meta[d] = {
            "title": str(row.get("ref_title", "") or ""),
            "first_author": str(row.get("ref_first_author", "") or ""),
            "year": yr,
            "cited_by_count": 0,
            "abstract": "",
        }

# Load KMeans semantic clusters (needed for CDM cluster identification)
print("Loading semantic clusters...")
sem_df = pd.read_csv(os.path.join(CATALOGS_DIR, "semantic_clusters.csv"))
sem_df["doi_norm"] = sem_df["doi"].apply(normalize_doi)
doi_to_cluster = dict(zip(sem_df["doi_norm"], sem_df["semantic_cluster"]))
print(f"Semantic clusters loaded: {len(sem_df)} papers")


# ============================================================
# Step 2: Select backbone papers
# ============================================================

CITE_THRESHOLD = 50
print(f"\nSelecting backbone (cited_by_count >= {CITE_THRESHOLD})...")

has_abs = works["abstract"].notna() & (works["abstract"].str.len() > 50)
high_cited = works[has_abs & (works["cited_by_count"] >= CITE_THRESHOLD)]
backbone_dois = set(high_cited["doi_norm"])

# Filter to papers with valid year
backbone_dois = {d for d in backbone_dois
                 if d in doi_meta and doi_meta[d]["year"] is not None
                 and 1985 <= (doi_meta[d]["year"] or 0) <= 2025}

print(f"Backbone papers (with valid year): {len(backbone_dois)}")


# ============================================================
# Step 3: Assign lineages (3 bands: CDM, Accountability, Efficiency)
# ============================================================

# Load bimodality pole scores if available
pole_path = os.path.join(TABLES_DIR, "tab_pole_papers.csv")
use_bimodal = os.path.exists(pole_path)

# CDM cluster ID (cluster 2 from KMeans labels — "cdm / projects / mechanism cdm")
CDM_CLUSTER = 2

# 3-band scheme
BAND_NAMES = {0: "CDM / Kyoto heritage", 1: "Accountability pole", 2: "Efficiency pole"}
BAND_COLORS_RGB = {0: "#F4A261", 1: "#457B9D", 2: "#E63946"}

if use_bimodal:
    print("Loading bimodality axis scores from tab_pole_papers.csv...")
    pole_df = pd.read_csv(pole_path)
    pole_df["doi_norm"] = pole_df["doi"].apply(normalize_doi)
    doi_to_score = dict(zip(pole_df["doi_norm"], pole_df["axis_score"]))
    print(f"  Pole scores for {len(doi_to_score)} papers")
else:
    print("WARNING: tab_pole_papers.csv not found. Run analyze_bimodality.py first.")
    print("Falling back to 6-cluster KMeans lineages.")
    doi_to_score = {}

n_communities = 3
lineage = {}
peripheral = set()

for d in backbone_dois:
    cluster = doi_to_cluster.get(d)
    score = doi_to_score.get(d, 0)

    if use_bimodal:
        if cluster == CDM_CLUSTER:
            lineage[d] = 0  # CDM heritage
        elif score < 0:
            lineage[d] = 1  # Accountability
        else:
            lineage[d] = 2  # Efficiency
    else:
        # Fallback: use KMeans cluster directly
        lineage[d] = doi_to_cluster.get(d, 0)

# Update community names for rendering
COMMUNITY_NAMES = BAND_NAMES

backbone_dois = {d for d in backbone_dois if d in lineage}
band_counts = {b: sum(1 for d in backbone_dois if lineage[d] == b) for b in range(n_communities)}
print(f"Final backbone: {len(backbone_dois)} papers")
for b, name in BAND_NAMES.items():
    print(f"  Band {b} ({name}): {band_counts.get(b, 0)} papers")


# ============================================================
# Step 4: Build citation DAG (internal links only)
# ============================================================

print("\nBuilding citation DAG...")
edges = []
for _, row in cit.iterrows():
    s = row["source_doi"]
    r = row["ref_doi"]
    if s in backbone_dois and r in backbone_dois:
        # Edge from cited (older) to citing (newer)
        edges.append((r, s))

# Deduplicate
edges = list(set(edges))
print(f"Internal citation edges: {len(edges)}")


# ============================================================
# Step 5: Layout computation
# ============================================================

print("\nComputing layout...")

# X = year (normalized to 0-1)
year_min = min(doi_meta[d]["year"] for d in backbone_dois)
year_max = max(doi_meta[d]["year"] for d in backbone_dois)

# Y = lineage band
# Order bands by median year of earliest papers (foundational at edges)
comm_median_years = {}
for c in range(n_communities):
    years_c = [doi_meta[d]["year"] for d in backbone_dois
               if lineage.get(d) == c and doi_meta[d]["year"] is not None]
    if years_c:
        comm_median_years[c] = np.median(years_c)
    else:
        comm_median_years[c] = 2020

# Sort: foundational (old median) at top, recent at bottom
sorted_comms = sorted(comm_median_years.keys(), key=lambda c: comm_median_years[c])
comm_to_band = {c: i for i, c in enumerate(sorted_comms)}

# Compute positions
positions = {}
band_height = 1.0 / max(n_communities, 1)

# Count papers per (community, year) for jittering
from collections import defaultdict
comm_year_counts = defaultdict(int)
comm_year_assigned = defaultdict(int)

for d in backbone_dois:
    c = lineage[d]
    yr = doi_meta[d]["year"]
    comm_year_counts[(c, int(yr))] += 1

for d in backbone_dois:
    c = lineage[d]
    yr = doi_meta[d]["year"]
    band = comm_to_band[c]

    # X position: year
    x = (yr - year_min) / max(year_max - year_min, 1)

    # Y position: band center + jitter
    band_center = (band + 0.5) * band_height
    n_in_slot = comm_year_counts[(c, int(yr))]
    idx_in_slot = comm_year_assigned[(c, int(yr))]
    comm_year_assigned[(c, int(yr))] += 1

    # Spread papers within band
    jitter_range = band_height * 0.35
    if n_in_slot > 1:
        jitter = -jitter_range + 2 * jitter_range * idx_in_slot / (n_in_slot - 1)
    else:
        jitter = 0
    y = band_center + jitter

    positions[d] = (x, y)


# ============================================================
# Step 6: Render figure
# ============================================================

import matplotlib
matplotlib.rcParams['font.size'] = 8

# Build palette from band colors
from matplotlib.colors import to_rgba
palette = {c: to_rgba(BAND_COLORS_RGB[c]) for c in range(n_communities)}

fig, ax = plt.subplots(figsize=(16, 10))

# Period bands
for i in range(len(PERIOD_BOUNDS) - 1):
    x0 = (PERIOD_BOUNDS[i] - year_min) / max(year_max - year_min, 1)
    x1 = (PERIOD_BOUNDS[i + 1] - year_min) / max(year_max - year_min, 1)
    ax.axvspan(x0, x1, alpha=0.15, color=PERIOD_COLORS[i], zorder=0)
    # Period label at top
    xmid = (x0 + x1) / 2
    ax.text(xmid, 1.02, PERIOD_LABELS[i], ha="center", va="bottom",
            fontsize=8, color="grey", transform=ax.transAxes if False else ax.transData)

# COP event markers
for yr, label in COP_EVENTS.items():
    if year_min <= yr <= year_max:
        x = (yr - year_min) / max(year_max - year_min, 1)
        ax.axvline(x, color="grey", linestyle="--", alpha=0.3, linewidth=0.7)
        ax.text(x, 1.01, label, ha="center", va="bottom", fontsize=6,
                color="grey", rotation=45)

# Draw citation edges (thin lines)
for src, tgt in edges:
    if src in positions and tgt in positions:
        x0, y0 = positions[src]
        x1, y1 = positions[tgt]
        src_comm = lineage.get(src)
        tgt_comm = lineage.get(tgt)

        if src_comm == tgt_comm:
            # Within-lineage: solid, colored
            color = BAND_COLORS_RGB.get(src_comm, "grey")
            alpha = 0.15
            style = "-"
        else:
            # Cross-lineage: grey dashed
            color = "grey"
            alpha = 0.08
            style = "--"

        ax.plot([x0, x1], [y0, y1], linestyle=style, color=color,
                alpha=alpha, linewidth=0.3, zorder=1)

# Identify top cross-lineage citations for highlight
cross_edges = [(s, t) for s, t in edges
               if s in lineage and t in lineage and lineage[s] != lineage[t]]

# Score by citation count of target
cross_scored = []
for s, t in cross_edges:
    score = doi_meta.get(t, {}).get("cited_by_count", 0) + doi_meta.get(s, {}).get("cited_by_count", 0)
    cross_scored.append((s, t, score))
cross_scored.sort(key=lambda x: -x[2])

# Draw top 15 cross-lineage arcs
for s, t, _ in cross_scored[:15]:
    if s in positions and t in positions:
        x0, y0 = positions[s]
        x1, y1 = positions[t]
        # Bezier arc
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2 + 0.05 * (1 if y0 < y1 else -1)
        verts = [(x0, y0), (cx, cy), (x1, y1)]
        codes = [Path.MOVETO, Path.CURVE3, Path.CURVE3]
        path = Path(verts, codes)
        patch = mpatches.PathPatch(
            path, facecolor="none", edgecolor="#E63946",
            linewidth=0.6, alpha=0.4, linestyle="--", zorder=2,
        )
        ax.add_patch(patch)

# Draw nodes
for d in backbone_dois:
    if d not in positions:
        continue
    x, y = positions[d]
    c = lineage[d]
    cit_count = doi_meta.get(d, {}).get("cited_by_count", 0)

    size = 10 + 60 * np.sqrt(max(cit_count, 0) / 200)
    alpha = 0.3 if d in peripheral else 0.8

    ax.scatter(x, y, s=size, color=[palette[c]], alpha=alpha,
               edgecolors="white", linewidths=0.3, zorder=3)

# Labels for top papers
n_labels = 40
top_papers = sorted(backbone_dois,
                    key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0),
                    reverse=True)[:n_labels]

label_positions = []
for d in top_papers:
    if d not in positions:
        continue
    x, y = positions[d]
    meta = doi_meta.get(d, {})
    author = str(meta.get("first_author", ""))
    # Clean author name
    author = author.split(",")[0].split(";")[0].strip()
    if not author or author in ("nan", ""):
        continue
    yr = meta.get("year", "")
    if yr and not np.isnan(yr):
        yr = int(yr)
    else:
        continue

    label = f"{author} ({yr})"

    # Simple offset: alternate up/down based on position in list
    idx = top_papers.index(d)
    offset_y = 0.012 if idx % 2 == 0 else -0.012

    ax.annotate(
        label,
        (x, y),
        xytext=(3, offset_y * 500),
        textcoords="offset points",
        fontsize=5.5,
        color="black",
        ha="left",
        va="center",
        path_effects=[pe.withStroke(linewidth=2, foreground="white")],
        zorder=4,
    )

# Legend: right-side labels aligned to lineage bands (same style as alluvial)
for c in sorted_comms:
    band = comm_to_band[c]
    band_center = (band + 0.5) * band_height
    name = COMMUNITY_NAMES.get(c, f"Cluster {c}")
    label_text = name.replace(" / ", "\n")
    n = sum(1 for d in backbone_dois if lineage.get(d) == c)
    label_text += f"\n(n={n})"
    r, g, b, _ = palette[c]
    dark_color = (r * 0.6, g * 0.6, b * 0.6)
    ax.text(1.02, band_center, label_text, ha="left", va="center",
            fontsize=5.5, linespacing=1.3, color=dark_color,
            transform=ax.transData)

# Year axis
year_ticks = list(range(int(year_min) - int(year_min) % 5, int(year_max) + 5, 5))
for yr in year_ticks:
    x = (yr - year_min) / max(year_max - year_min, 1)
    if 0 <= x <= 1:
        ax.text(x, -0.02, str(yr), ha="center", va="top", fontsize=7, color="grey")

ax.set_xlim(-0.02, 1.28)
ax.set_ylim(-0.05, 1.05)

n_backbone = len(backbone_dois)
ax.set_title(
    f"Citation genealogy of climate finance scholarship ({n_backbone} most-cited papers)\n"
    "Node size ∝ √citations · Cross-lineage arcs in red",
    fontsize=12, pad=20,
)
ax.axis("off")

plt.tight_layout()
fig_path = os.path.join(FIGURES_DIR, "fig_genealogy")
save_figure(fig, fig_path, no_pdf=args.no_pdf)
plt.close()


# ============================================================
# Step 6b: Interactive HTML version with reference popups
# ============================================================

import html as html_mod

# Select papers that get popups: top 100 most-cited + all labelled
popup_dois = set(sorted(backbone_dois,
                        key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0),
                        reverse=True)[:100])
popup_dois.update(top_papers)  # all labelled papers (top 40)

# SVG dimensions
svg_w, svg_h = 1400, 900
pad_l, pad_r, pad_t, pad_b = 60, 320, 70, 45
chart_w = svg_w - pad_l - pad_r
chart_h = svg_h - pad_t - pad_b

def to_sx(xnorm):
    return pad_l + xnorm * chart_w

def to_sy(ynorm):
    return pad_t + chart_h - ynorm * chart_h

palette_hex = {c: BAND_COLORS_RGB[c] for c in range(n_communities)}

def rgba_svg(c_idx, alpha=0.8):
    r, g, b, _ = palette[c_idx]
    return f"rgba({int(r*255)},{int(g*255)},{int(b*255)},{alpha})"

svg_parts = []
svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
                 f'font-family="sans-serif">')

# Background
svg_parts.append(f'<rect width="{svg_w}" height="{svg_h}" fill="white"/>')

# Title
n_backbone = len(backbone_dois)
svg_parts.append(f'<text x="{svg_w//2}" y="25" text-anchor="middle" font-size="15" font-weight="bold">'
                 f'Citation genealogy of climate finance scholarship ({n_backbone} most-cited papers)</text>')
svg_parts.append(f'<text x="{svg_w//2}" y="45" text-anchor="middle" font-size="11" fill="#666">'
                 f'Node size \u221d \u221acitations · Hover for full reference · Click to open DOI</text>')

# Period bands
for i in range(len(PERIOD_BOUNDS) - 1):
    x0 = to_sx((PERIOD_BOUNDS[i] - year_min) / max(year_max - year_min, 1))
    x1 = to_sx((PERIOD_BOUNDS[i + 1] - year_min) / max(year_max - year_min, 1))
    fill = "#f5f5f5" if i % 2 == 0 else "#ececec"
    svg_parts.append(f'<rect x="{x0:.1f}" y="{pad_t}" width="{x1-x0:.1f}" '
                     f'height="{chart_h}" fill="{fill}"/>')
    xmid = (x0 + x1) / 2
    svg_parts.append(f'<text x="{xmid:.1f}" y="{pad_t - 5}" text-anchor="middle" '
                     f'font-size="10" fill="#888">{PERIOD_LABELS[i]}</text>')

# COP event markers
for yr, label in COP_EVENTS.items():
    if year_min <= yr <= year_max:
        x = to_sx((yr - year_min) / max(year_max - year_min, 1))
        svg_parts.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t + chart_h}" '
                         f'stroke="#bbb" stroke-width="0.7" stroke-dasharray="4,3"/>')
        svg_parts.append(f'<text x="{x:.1f}" y="{pad_t - 15}" text-anchor="middle" '
                         f'font-size="8" fill="#999" transform="rotate(-30,{x:.1f},{pad_t - 15})">'
                         f'{label}</text>')

# Year axis ticks
year_ticks = list(range(int(year_min) - int(year_min) % 5, int(year_max) + 5, 5))
for yr in year_ticks:
    xn = (yr - year_min) / max(year_max - year_min, 1)
    if 0 <= xn <= 1:
        x = to_sx(xn)
        svg_parts.append(f'<text x="{x:.1f}" y="{pad_t + chart_h + 18}" text-anchor="middle" '
                         f'font-size="9" fill="#888">{yr}</text>')

# Citation edges (within-lineage only for clarity, skip cross for SVG performance)
for src, tgt in edges:
    if src in positions and tgt in positions:
        src_c = lineage.get(src)
        tgt_c = lineage.get(tgt)
        if src_c != tgt_c:
            continue  # skip cross-lineage for performance
        x0, y0 = positions[src]
        x1, y1 = positions[tgt]
        sx0, sy0 = to_sx(x0), to_sy(y0)
        sx1, sy1 = to_sx(x1), to_sy(y1)
        svg_parts.append(f'<line x1="{sx0:.1f}" y1="{sy0:.1f}" x2="{sx1:.1f}" y2="{sy1:.1f}" '
                         f'stroke="{palette_hex[src_c]}" stroke-width="0.3" opacity="0.15"/>')

# Top 15 cross-lineage arcs (highlighted)
for s, t, _ in cross_scored[:15]:
    if s in positions and t in positions:
        sx0, sy0 = to_sx(positions[s][0]), to_sy(positions[s][1])
        sx1, sy1 = to_sx(positions[t][0]), to_sy(positions[t][1])
        scx = (sx0 + sx1) / 2
        scy = (sy0 + sy1) / 2 + 30 * (1 if sy0 > sy1 else -1)
        svg_parts.append(f'<path d="M{sx0:.1f},{sy0:.1f} Q{scx:.1f},{scy:.1f} {sx1:.1f},{sy1:.1f}" '
                         f'fill="none" stroke="#E63946" stroke-width="0.8" opacity="0.4" '
                         f'stroke-dasharray="3,2"/>')

# Nodes — all backbone papers
# Sort so popup papers are drawn last (on top)
sorted_backbone = sorted(backbone_dois, key=lambda d: d in popup_dois)
for d in sorted_backbone:
    if d not in positions:
        continue
    x, y = positions[d]
    sx, sy = to_sx(x), to_sy(y)
    c = lineage[d]
    cit_count = doi_meta.get(d, {}).get("cited_by_count", 0)
    radius = 3 + 8 * np.sqrt(max(cit_count, 0) / 200)
    alpha = 0.3 if d in peripheral else 0.8

    if d in popup_dois:
        meta = doi_meta.get(d, {})
        author = html_mod.escape(str(meta.get("first_author", "?")))
        title = html_mod.escape(str(meta.get("title", "")))
        yr = int(meta["year"]) if meta.get("year") and not np.isnan(meta["year"]) else "?"
        cites = int(cit_count)
        doi_str = html_mod.escape(str(d))
        doi_url = f"https://doi.org/{d}" if d and d not in ("nan", "none", "") else ""
        tooltip = (f"<b>{author} ({yr})</b><br>"
                   f"<i>{title}</i><br>"
                   f"{cites} citations<br>"
                   f"<span style='color:#888;font-size:10px'>{doi_str}</span>")
        tooltip_attr = tooltip.replace('"', '&quot;')
        doi_attr = html_mod.escape(doi_url, quote=True)
        svg_parts.append(
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius:.1f}" '
            f'fill="{rgba_svg(c, alpha)}" stroke="white" stroke-width="0.5" '
            f'class="node" data-tooltip="{tooltip_attr}" data-doi="{doi_attr}" '
            f'style="cursor:pointer"/>')
    else:
        # Non-clickable: toned down
        svg_parts.append(
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius:.1f}" '
            f'fill="{rgba_svg(c, 0.15)}" stroke="none"/>')

# Labels for top papers (same as static figure)
for d in top_papers:
    if d not in positions:
        continue
    x, y = positions[d]
    sx, sy = to_sx(x), to_sy(y)
    meta = doi_meta.get(d, {})
    author = str(meta.get("first_author", ""))
    author = author.split(",")[0].split(";")[0].strip()
    if not author or author in ("nan", ""):
        continue
    yr = meta.get("year", "")
    if yr and not np.isnan(yr):
        yr = int(yr)
    else:
        continue
    label = html_mod.escape(f"{author} ({yr})")
    idx = list(top_papers).index(d)
    offset_y = -12 if idx % 2 == 0 else 12
    svg_parts.append(
        f'<text x="{sx + 4:.1f}" y="{sy + offset_y:.1f}" font-size="7.5" '
        f'fill="black" pointer-events="none">'
        f'<tspan stroke="white" stroke-width="2.5" paint-order="stroke">{label}</tspan></text>')

# Legend: right-side labels aligned to lineage bands (same style as alluvial)
legend_x = pad_l + chart_w + 15
for c in sorted_comms:
    band = comm_to_band[c]
    band_center_y = to_sy((band + 0.5) * band_height)
    name = COMMUNITY_NAMES.get(c, f"Cluster {c}")
    label_lines = name.split(" / ")
    n = sum(1 for d in backbone_dois if lineage.get(d) == c)
    label_lines.append(f"(n={n})")
    line_h = 15
    start_y = band_center_y - (len(label_lines) - 1) * line_h / 2
    pr, pg, pb, _ = palette[c]
    dark = f"rgb({int(pr*255*0.6)},{int(pg*255*0.6)},{int(pb*255*0.6)})"
    for li, line in enumerate(label_lines):
        weight = "normal" if li < len(label_lines) - 1 else "normal"
        fill = dark if li < len(label_lines) - 1 else "#888"
        fsize = "11" if li < len(label_lines) - 1 else "9"
        svg_parts.append(
            f'<text x="{legend_x}" y="{start_y + li * line_h:.1f}" '
            f'font-size="{fsize}" fill="{fill}" dominant-baseline="central">'
            f'{html_mod.escape(line)}</text>')

svg_parts.append('</svg>')

# Build HTML
html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Fig 4 – Citation genealogy (interactive)</title>
<style>
body {{ margin: 20px; font-family: sans-serif; background: #fafafa; }}
#container {{ position: relative; display: inline-block; }}
#tooltip {{
  display: none; position: absolute; pointer-events: none;
  background: white; border: 1px solid #ccc; border-radius: 6px;
  padding: 12px 16px; font-size: 12px; line-height: 1.5;
  box-shadow: 2px 2px 8px rgba(0,0,0,0.15); max-width: 480px; z-index: 10;
}}
.node:hover {{ filter: brightness(0.85); stroke: #333 !important; stroke-width: 1.5px !important; }}
</style>
</head><body>
<div id="container">
{''.join(svg_parts)}
<div id="tooltip"></div>
</div>
<script>
const tooltip = document.getElementById('tooltip');
document.querySelectorAll('.node').forEach(el => {{
  el.addEventListener('mouseenter', e => {{
    tooltip.innerHTML = el.dataset.tooltip;
    tooltip.style.display = 'block';
  }});
  el.addEventListener('mousemove', e => {{
    const box = document.getElementById('container').getBoundingClientRect();
    let left = e.clientX - box.left + 15;
    let top = e.clientY - box.top - 60;
    if (left + 350 > box.width) left = e.clientX - box.left - 370;
    if (top < 0) top = e.clientY - box.top + 20;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }});
  el.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
  el.addEventListener('click', () => {{
    const doi = el.dataset.doi;
    if (doi) window.open(doi, '_blank');
  }});
}});
</script>
</body></html>"""

html_path = os.path.join(FIGURES_DIR, "fig_genealogy.html")
with open(html_path, "w") as f:
    f.write(html_content)
print(f"Saved interactive version → figures/fig_genealogy.html")


# ============================================================
# Step 7: Save lineage table
# ============================================================

rows = []
for d in backbone_dois:
    meta = doi_meta.get(d, {})
    rows.append({
        "doi": d,
        "lineage": lineage.get(d, -1),
        "lineage_name": COMMUNITY_NAMES.get(lineage.get(d, -1), "Unknown"),
        "peripheral": d in peripheral,
        "first_author": meta.get("first_author", ""),
        "year": meta.get("year", ""),
        "cited_by_count": meta.get("cited_by_count", 0),
        "title": meta.get("title", "")[:100],
    })

lineage_df = pd.DataFrame(rows).sort_values(["lineage", "cited_by_count"], ascending=[True, False])
lineage_df.to_csv(os.path.join(TABLES_DIR, "tab_lineages.csv"), index=False)
print(f"Saved lineage table → tables/tab_lineages.csv ({len(lineage_df)} papers)")


# ============================================================
# Robustness: Louvain resolution sensitivity (R3)
# ============================================================

if args.robustness:
    print("\n=== Robustness: Louvain resolution sensitivity ===")
    import community as community_louvain
    import networkx as nx
    from sklearn.metrics import adjusted_rand_score

    # Rebuild co-citation network (from analyze_cocitation.py logic)
    from scipy.sparse import lil_matrix

    ref_counts = cit.groupby("ref_doi").size().sort_values(ascending=False)
    TOP_N = 200
    top_refs = ref_counts.head(TOP_N).index.tolist()
    top_set = set(top_refs)
    ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}

    source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)
    cocit_matrix = lil_matrix((TOP_N, TOP_N), dtype=np.float64)

    for source_doi, ref_list in source_groups.items():
        refs_in_top = [r for r in ref_list if r in top_set]
        if len(refs_in_top) < 2:
            continue
        for i in range(len(refs_in_top)):
            for j in range(i + 1, len(refs_in_top)):
                a = ref_to_idx[refs_in_top[i]]
                b = ref_to_idx[refs_in_top[j]]
                cocit_matrix[a, b] += 1
                cocit_matrix[b, a] += 1

    cocit_dense = cocit_matrix.toarray()

    G = nx.Graph()
    for i, doi in enumerate(top_refs):
        G.add_node(doi)
    MIN_COCIT = 3
    for i in range(TOP_N):
        for j in range(i + 1, TOP_N):
            w = cocit_dense[i, j]
            if w >= MIN_COCIT:
                G.add_edge(top_refs[i], top_refs[j], weight=w)
    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)

    # Test resolution parameters
    resolutions = [0.5, 1.0, 1.5, 2.0]
    partitions = {}

    try:
        for gamma in resolutions:
            part = community_louvain.best_partition(G, weight="weight",
                                                     resolution=gamma, random_state=42)
            partitions[gamma] = part
            n_c = len(set(part.values()))
            print(f"  γ={gamma}: {n_c} communities")

        # Build sensitivity table
        common_nodes = list(G.nodes())
        sens_rows = []
        for doi in common_nodes:
            row = {"doi": doi}
            for gamma in resolutions:
                row[f"community_g{str(gamma).replace('.', '')}"] = partitions[gamma].get(doi, -1)
            sens_rows.append(row)

        sens_df = pd.DataFrame(sens_rows)
        sens_df.to_csv(os.path.join(TABLES_DIR, "tab_louvain_sensitivity.csv"), index=False)
        print(f"Saved Louvain sensitivity → tables/tab_louvain_sensitivity.csv")

        # ARI between resolution levels
        print("\n  Pairwise ARI:")
        for i, g1 in enumerate(resolutions):
            for g2 in resolutions[i + 1:]:
                labels1 = [partitions[g1][n] for n in common_nodes]
                labels2 = [partitions[g2][n] for n in common_nodes]
                ari = adjusted_rand_score(labels1, labels2)
                print(f"    γ={g1} vs γ={g2}: ARI={ari:.3f}")

    except TypeError:
        print("  WARNING: community_louvain.best_partition does not support 'resolution' parameter.")
        print("  Skipping R3 sensitivity analysis.")

print("\nDone.")
