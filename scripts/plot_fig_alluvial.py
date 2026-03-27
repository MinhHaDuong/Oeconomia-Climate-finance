"""Render the alluvial figure and interactive HTML.

Reads:  content/tables/tab_alluvial.csv
        data/catalogs/cluster_labels.json
        content/tables/tab_core_shares.csv  (optional: full corpus only, for "% core" labels)
Writes: content/figures/fig_alluvial.png  (and core/censor variants)
        content/figures/fig_alluvial.html  (interactive version with paper tooltips)

Flags: --core-only, --censor-gap N, --no-pdf

Run compute_alluvial.py first to generate the input tables.
"""

import argparse
import html as html_mod
import json
import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path
from utils import BASE_DIR, get_logger, load_analysis_config, save_figure

log = get_logger("plot_fig_alluvial")

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

_cfg = load_analysis_config()
CITE_THRESHOLD = _cfg["clustering"]["cite_threshold"]

# --- Args ---
parser = argparse.ArgumentParser(description="Render alluvial figure and interactive HTML")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
parser.add_argument("--core-only", action="store_true",
                    help="Use core-only variant of input tables")
parser.add_argument("--censor-gap", type=int, default=0,
                    help="Load censor-gap variant of input tables (affects FIG_AL name only)")
args = parser.parse_args()

# Output naming mirrors compute_alluvial.py
if args.core_only:
    FIG_AL = "fig_alluvial_core"
    TAB_AL = "tab_alluvial_core.csv"
    LABEL_FILE = "cluster_labels_core.json"
else:
    FIG_AL = "fig_alluvial"
    TAB_AL = "tab_alluvial.csv"
    LABEL_FILE = "cluster_labels.json"

if args.censor_gap > 0:
    FIG_AL += f"_censor{args.censor_gap}"

# --- Load tables ---
alluvial_data = pd.read_csv(os.path.join(TABLES_DIR, TAB_AL), index_col=0)
alluvial_data.columns = alluvial_data.columns.astype(int)
period_labels = alluvial_data.index.tolist()
n_periods = len(period_labels)
n_clusters = len(alluvial_data.columns)

with open(os.path.join(TABLES_DIR, LABEL_FILE)) as f:
    cluster_labels_raw = json.load(f)
cluster_labels = {int(k): v for k, v in cluster_labels_raw.items()}

# Core share per cell (full corpus only, for "% core" annotations)
core_crosstab = None
if not args.core_only:
    shares_path = os.path.join(TABLES_DIR, "tab_core_shares.csv")
    if os.path.exists(shares_path):
        core_crosstab = pd.read_csv(shares_path, index_col=0)
        core_crosstab.columns = core_crosstab.columns.astype(int)

# --- Palette and layout constants ---
palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))

# X positions for period columns (leave room for legend on right)
x_positions = np.linspace(0, 0.62, n_periods)
col_width = 0.04  # Half-width of each column bar

# SVG dimensions (used by both the HTML step and SVG helpers below)
svg_w, svg_h = 1350, 675
pad_l, pad_r, pad_t, pad_b = 75, 420, 82, 52
chart_w = svg_w - pad_l - pad_r
chart_h = svg_h - pad_t - pad_b


# SVG coordinate helpers (moved here from mid-file for clarity)
def to_sx(xnorm):
    return pad_l + (xnorm / 0.62) * chart_w

def to_sy(ynorm):
    return pad_t + chart_h - (ynorm / 1.0) * chart_h

def rgba(c_idx, alpha=0.9):
    r, g, b, _ = palette[c_idx]
    return f"rgba({int(r*255)},{int(g*255)},{int(b*255)},{alpha})"

def rgb_dark(c_idx, factor=0.6):
    r, g, b, _ = palette[c_idx]
    return f"rgb({int(r*255*factor)},{int(g*255*factor)},{int(b*255*factor)})"


# --- Compute period stacks (shared by Step 7 and Step 7b) ---
period_stacks = {}
for pi, period in enumerate(period_labels):
    total = alluvial_data.loc[period].sum() if period in alluvial_data.index else 0
    if total == 0:
        period_stacks[period] = {}
        continue
    max_height = 0.9
    y_bottom = 0.05
    stacks = {}
    for c in range(n_clusters):
        count = alluvial_data.loc[period, c] if period in alluvial_data.index else 0
        height = (count / total) * max_height
        stacks[c] = {"bottom": y_bottom, "height": height, "count": count}
        y_bottom += height
    period_stacks[period] = stacks

last_stacks = period_stacks[period_labels[-1]]


# ============================================================
# Step 7: Render alluvial figure
# ============================================================

fig, ax = plt.subplots(figsize=(7, 3.5))

# Draw column bars
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    stacks = period_stacks[period]
    for c in range(n_clusters):
        if c not in stacks:
            continue
        s = stacks[c]
        if s["height"] > 0:
            rect = plt.Rectangle(
                (x - col_width, s["bottom"]), 2 * col_width, s["height"],
                facecolor=palette[c], edgecolor="white", linewidth=0.5, alpha=0.9,
            )
            ax.add_patch(rect)
            # Label if tall enough
            if s["height"] > 0.04:
                label = f'{s["count"]}'
                if not args.core_only and core_crosstab is not None:
                    n_core = int(core_crosstab.loc[period, c]) if period in core_crosstab.index else 0
                    pct = n_core / s["count"] * 100 if s["count"] > 0 else 0
                    label += f'\n({pct:.0f}% core)'
                ax.text(x, s["bottom"] + s["height"] / 2,
                        label, ha="center", va="center",
                        fontsize=4.5, color="black", fontweight="bold",
                        linespacing=1.2)

# Draw flows between adjacent periods
for pi in range(n_periods - 1):
    period_a = period_labels[pi]
    period_b = period_labels[pi + 1]
    x_a = x_positions[pi] + col_width
    x_b = x_positions[pi + 1] - col_width

    stacks_a = period_stacks[period_a]
    stacks_b = period_stacks[period_b]

    for c in range(n_clusters):
        if c not in stacks_a or c not in stacks_b:
            continue
        sa = stacks_a[c]
        sb = stacks_b[c]
        if sa["height"] <= 0 or sb["height"] <= 0:
            continue

        # Draw curved ribbon from cluster c in period_a to cluster c in period_b
        y_a_bot = sa["bottom"]
        y_a_top = sa["bottom"] + sa["height"]
        y_b_bot = sb["bottom"]
        y_b_top = sb["bottom"] + sb["height"]

        # Bezier control points for smooth flow
        cx1 = x_a + (x_b - x_a) * 0.4
        cx2 = x_a + (x_b - x_a) * 0.6

        # Top edge
        verts_top = [
            (x_a, y_a_top), (cx1, y_a_top), (cx2, y_b_top), (x_b, y_b_top),
        ]
        # Bottom edge (reversed)
        verts_bot = [
            (x_b, y_b_bot), (cx2, y_b_bot), (cx1, y_a_bot), (x_a, y_a_bot),
        ]
        verts = verts_top + verts_bot + [(x_a, y_a_top)]  # close path
        codes = (
            [Path.MOVETO] + [Path.CURVE4] * 3 +
            [Path.LINETO] + [Path.CURVE4] * 3 +
            [Path.CLOSEPOLY]
        )
        path = Path(verts, codes)
        patch = mpatches.PathPatch(
            path, facecolor=palette[c], alpha=0.35, edgecolor="none",
        )
        ax.add_patch(patch)

# Period labels
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    ax.text(x, -0.03, period, ha="center", va="top", fontsize=6, fontweight="bold")

# Legend: labels with leader lines, evenly spaced to avoid overlap
label_items = []
for c in range(n_clusters):
    if c not in last_stacks:
        continue
    s = last_stacks[c]
    if s["height"] <= 0:
        continue
    label_text = cluster_labels.get(c, f"Cluster {c}").replace(" / ", "\n")
    n_lines = label_text.count("\n") + 1
    label_items.append({
        "c": c, "y_band": s["bottom"] + s["height"] / 2,
        "text": label_text, "height": n_lines * 0.026,
    })

# Evenly space labels across the full chart height
label_items.sort(key=lambda it: it["y_band"])
n_labels = len(label_items)
total_label_height = sum(it["height"] for it in label_items)
spacing = (0.95 - total_label_height) / max(n_labels - 1, 1)
y_cursor = 0.02
for it in label_items:
    it["y_label"] = y_cursor + it["height"] / 2
    y_cursor += it["height"] + spacing

x_bar_edge = x_positions[-1] + col_width
x_label = x_bar_edge + 0.06
for it in label_items:
    # Leader line from band midpoint to label
    ax.annotate(
        "", xy=(x_bar_edge + 0.003, it["y_band"]),
        xytext=(x_label - 0.005, it["y_label"]),
        arrowprops=dict(arrowstyle="-", color=palette[it["c"]] * 0.6,
                        lw=0.7, connectionstyle="arc3,rad=0.0"),
    )
    ax.text(x_label, it["y_label"],
            it["text"], ha="left", va="center", fontsize=5.5,
            linespacing=1.3, color=palette[it["c"]] * 0.6)

ax.set_xlim(-0.06, 0.95)
ax.set_ylim(-0.06, 1.0)
total = int(alluvial_data.values.sum())
core_label = f"core papers cited ≥ {CITE_THRESHOLD}, " if args.core_only else ""
ax.set_title(
    f"Thematic recomposition of scholarship around climate finance, 1990–2024\n"
    f"({core_label}N = {total:,} publications; band width = number of publications per thematic cluster)",
    fontsize=7, pad=8,
)
ax.axis("off")

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, FIG_AL), no_pdf=args.no_pdf)
log.info("  (%s)", FIG_AL)
plt.close()


# ============================================================
# Step 7b: Interactive HTML version with paper tooltips
# ============================================================

# We need the original df to get top-cited papers per cell.
# Load it from refined_works.csv and reconstruct period/cluster assignments
# using the same logic as compute_alluvial.py.

# Check if we can reconstruct paper data for tooltips
try:
    import pandas as _pd
    from sklearn.cluster import KMeans as _KMeans
    from utils import CATALOGS_DIR as _CATALOGS_DIR
    from utils import load_analysis_config as _load_cfg
    from utils import load_refined_embeddings as _load_embeddings

    _alluvial_cfg = _load_cfg()
    _alluvial_ymin = _alluvial_cfg["periodization"]["year_min"]
    _alluvial_ymax = _alluvial_cfg["periodization"]["year_max"]
    _works = _pd.read_csv(os.path.join(_CATALOGS_DIR, "refined_works.csv"))
    _works["year"] = _pd.to_numeric(_works["year"], errors="coerce")
    _has_title = _works["title"].notna() & (_works["title"].str.len() > 0)
    _in_range = (_works["year"] >= _alluvial_ymin) & (_works["year"] <= _alluvial_ymax)
    _df = _works[_has_title & _in_range].copy().reset_index(drop=True)
    _embeddings = _load_embeddings()

    if len(_embeddings) != len(_df):
        raise RuntimeError("Embedding size mismatch")

    _df["cited_by_count"] = _pd.to_numeric(_df["cited_by_count"], errors="coerce").fillna(0)
    if args.core_only:
        _core_mask = _df["cited_by_count"] >= CITE_THRESHOLD
        _core_indices = _df.index[_core_mask].values
        _df = _df.loc[_core_mask].reset_index(drop=True)
        _embeddings = _embeddings[_core_indices]

    # Fit KMeans with same seed to reproduce cluster assignments
    _km = _KMeans(n_clusters=n_clusters, random_state=42, n_init=20)
    _df["cluster"] = _km.fit_predict(_embeddings)

    # Assign periods using alluvial_data index order
    # Derive boundaries from period_labels (e.g. "1990–2006" → start=1990, end=2006)
    _bounds = []
    for _lbl in period_labels:
        _lo, _hi = [int(x) for x in _lbl.replace("–", "-").split("-")]
        _bounds.append((_lo, _hi))

    def _assign_period(yr):
        for _lbl, (_lo, _hi) in zip(period_labels, _bounds):
            if _lo <= yr <= _hi:
                return _lbl
        return period_labels[-1]

    _df["period"] = _df["year"].apply(_assign_period)
    _have_paper_data = True
except Exception as _e:
    log.info("  (skipping interactive HTML: %s)", _e)
    _have_paper_data = False

if _have_paper_data:
    # Collect top-3 most-cited papers per (period, cluster)
    top_papers = {}
    for period in period_labels:
        for c in range(n_clusters):
            cell = _df[(_df["period"] == period) & (_df["cluster"] == c)]
            cell_sorted = cell.sort_values("cited_by_count", ascending=False).head(3)
            papers = []
            for _, row in cell_sorted.iterrows():
                author = str(row.get("first_author", "?"))
                if len(author) > 25:
                    author = author[:23] + "…"
                yr = int(row["year"]) if _pd.notna(row["year"]) else "?"
                title = str(row.get("title", ""))
                if len(title) > 80:
                    title = title[:78] + "…"
                cites = int(row["cited_by_count"]) if _pd.notna(row["cited_by_count"]) else 0
                papers.append(f"{author} ({yr}), {title} [{cites} cit.]")
            top_papers[(period, c)] = papers

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
                      f'font-family="sans-serif">')

    # Title
    total = int(alluvial_data.values.sum())
    svg_parts.append(f'<text x="{svg_w//2}" y="28" text-anchor="middle" font-size="16" font-weight="bold">'
                     f'Thematic recomposition of scholarship around climate finance, 1990–2024</text>')
    svg_parts.append(f'<text x="{svg_w//2}" y="50" text-anchor="middle" font-size="13" fill="#666">'
                     f'(N = {total:,} publications; hover over a cell to see top-cited papers)</text>')

    # Flow ribbons (draw first, behind bars)
    for pi in range(n_periods - 1):
        pa, pb = period_labels[pi], period_labels[pi + 1]
        xa = x_positions[pi]
        xb = x_positions[pi + 1]
        sa_all, sb_all = period_stacks[pa], period_stacks[pb]
        cw = col_width
        for c in range(n_clusters):
            if c not in sa_all or c not in sb_all:
                continue
            sa, sb = sa_all[c], sb_all[c]
            if sa["height"] <= 0 or sb["height"] <= 0:
                continue
            x1 = to_sx(xa + cw)
            x2 = to_sx(xb - cw)
            y1t, y1b = to_sy(sa["bottom"] + sa["height"]), to_sy(sa["bottom"])
            y2t, y2b = to_sy(sb["bottom"] + sb["height"]), to_sy(sb["bottom"])
            cx1 = x1 + (x2 - x1) * 0.4
            cx2 = x1 + (x2 - x1) * 0.6
            d = (f"M{x1},{y1t} C{cx1},{y1t} {cx2},{y2t} {x2},{y2t} "
                 f"L{x2},{y2b} C{cx2},{y2b} {cx1},{y1b} {x1},{y1b} Z")
            svg_parts.append(f'<path d="{d}" fill="{rgba(c, 0.3)}" stroke="none"/>')

    # Column bars (clickable)
    for pi, period in enumerate(period_labels):
        x = x_positions[pi]
        stacks = period_stacks[period]
        for c in range(n_clusters):
            if c not in stacks:
                continue
            s = stacks[c]
            if s["height"] <= 0:
                continue
            rx = to_sx(x - col_width)
            ry = to_sy(s["bottom"] + s["height"])
            rw = to_sx(x + col_width) - rx
            rh = to_sy(s["bottom"]) - ry
            cell_id = f"cell_{pi}_{c}"
            paper_lines = "<br>".join(html_mod.escape(p) for p in top_papers.get((period, c), ["(no papers)"]))
            cluster_name = html_mod.escape(cluster_labels.get(c, f"Cluster {c}"))
            # Build tooltip HTML, then escape quotes for embedding in attribute
            tooltip_inner = (f'<b>{period} — {cluster_name}</b><br>'
                             f'<b>{s["count"]} publications</b><br><br>'
                             f'{paper_lines}')
            tooltip_attr = tooltip_inner.replace('"', '&quot;')
            svg_parts.append(
                f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
                f'fill="{rgba(c)}" stroke="white" stroke-width="0.5" '
                f'class="cell" data-tooltip="{tooltip_attr}" '
                f'style="cursor:pointer"/>'
            )
            # Count label
            if s["height"] > 0.04:
                tx = to_sx(x)
                ty = to_sy(s["bottom"] + s["height"] / 2)
                svg_parts.append(
                    f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                    f'dominant-baseline="central" font-size="12" font-weight="bold" '
                    f'fill="black" pointer-events="none">{s["count"]}</text>'
                )

    # Period labels
    for pi, period in enumerate(period_labels):
        tx = to_sx(x_positions[pi])
        svg_parts.append(f'<text x="{tx:.1f}" y="{svg_h - 18}" text-anchor="middle" '
                         f'font-size="14" font-weight="bold">{period}</text>')

    # Legend labels next to last column
    for c in range(n_clusters):
        if c not in last_stacks:
            continue
        s = last_stacks[c]
        if s["height"] <= 0:
            continue
        label_lines = cluster_labels.get(c, f"Cluster {c}").split(" / ")
        base_y = to_sy(s["bottom"] + s["height"] / 2)
        lx = to_sx(x_positions[-1] + col_width) + 12
        # Vertically center the multi-line label
        line_h = 17
        start_y = base_y - (len(label_lines) - 1) * line_h / 2
        for li, line in enumerate(label_lines):
            svg_parts.append(
                f'<text x="{lx:.1f}" y="{start_y + li * line_h:.1f}" '
                f'font-size="12" fill="{rgb_dark(c)}" dominant-baseline="central">'
                f'{html_mod.escape(line)}</text>'
            )

    svg_parts.append('</svg>')

    # Build full HTML with tooltip logic
    html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Fig 3 – Alluvial (interactive)</title>
<style>
body {{ margin: 20px; font-family: sans-serif; background: #fafafa; }}
#container {{ position: relative; display: inline-block; }}
#tooltip {{
  display: none; position: absolute; pointer-events: none;
  background: white; border: 1px solid #ccc; border-radius: 6px;
  padding: 14px 18px; font-size: 13px; line-height: 1.5;
  box-shadow: 2px 2px 8px rgba(0,0,0,0.15); max-width: 520px; z-index: 10;
}}
.cell:hover {{ filter: brightness(0.9); }}
</style>
</head><body>
<div id="container">
{''.join(svg_parts)}
<div id="tooltip"></div>
</div>
<script>
const tooltip = document.getElementById('tooltip');
document.querySelectorAll('.cell').forEach(el => {{
  el.addEventListener('mouseenter', e => {{
    tooltip.innerHTML = el.dataset.tooltip;
    tooltip.style.display = 'block';
  }});
  el.addEventListener('mousemove', e => {{
    const box = document.getElementById('container').getBoundingClientRect();
    let left = e.clientX - box.left + 15;
    let top = e.clientY - box.top + 10;
    if (left + 300 > box.width) left = e.clientX - box.left - 320;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }});
  el.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
}});
</script>
</body></html>"""

    html_path = os.path.join(FIGURES_DIR, f"{FIG_AL}.html")
    with open(html_path, "w") as f:
        f.write(html_content)
    log.info("Saved interactive version -> figures/%s.html", FIG_AL)

log.info("Done.")
