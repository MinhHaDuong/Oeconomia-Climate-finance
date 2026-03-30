"""Interactive HTML alluvial diagram with hover tooltips.

Reads:
  content/tables/tab_alluvial.csv — period × cluster counts
  data/catalogs/cluster_labels.json — human-readable cluster names

Produces:
  content/figures/fig_alluvial.html — interactive SVG with paper tooltips
"""

import argparse
import html as html_mod
import json
import os

import numpy as np
import pandas as pd
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, load_analysis_config

log = get_logger("plot_alluvial_html")

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

_cfg = load_analysis_config()
CITE_THRESHOLD = _cfg["clustering"]["cite_threshold"]


def load_data(core_only=False, censor_gap=0):
    """Load alluvial tables and cluster labels."""
    if core_only:
        tab_file = "tab_alluvial_core.csv"
        label_file = "cluster_labels_core.json"
        fig_name = "fig_alluvial_core"
    else:
        tab_file = "tab_alluvial.csv"
        label_file = "cluster_labels.json"
        fig_name = "fig_alluvial"

    if censor_gap > 0:
        fig_name += f"_censor{censor_gap}"

    alluvial_data = pd.read_csv(os.path.join(TABLES_DIR, tab_file), index_col=0)
    alluvial_data.columns = alluvial_data.columns.astype(int)

    with open(os.path.join(TABLES_DIR, label_file)) as f:
        cluster_labels_raw = json.load(f)
    cluster_labels = {int(k): v for k, v in cluster_labels_raw.items()}

    return alluvial_data, cluster_labels, fig_name


def compute_stacks(alluvial_data):
    """Compute period stacks from alluvial data."""
    period_labels = alluvial_data.index.tolist()
    n_clusters = len(alluvial_data.columns)
    period_stacks = {}
    for period in period_labels:
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
    return period_stacks


def load_paper_data(alluvial_data, cluster_labels, core_only):
    """Load refined works and reconstruct period/cluster assignments for tooltips."""
    n_clusters = len(alluvial_data.columns)
    period_labels = alluvial_data.index.tolist()

    try:
        from sklearn.cluster import KMeans
        from utils import CATALOGS_DIR, load_refined_embeddings

        cfg = load_analysis_config()
        ymin = cfg["periodization"]["year_min"]
        ymax = cfg["periodization"]["year_max"]
        works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
        works["year"] = pd.to_numeric(works["year"], errors="coerce")
        has_title = works["title"].notna() & (works["title"].str.len() > 0)
        in_range = (works["year"] >= ymin) & (works["year"] <= ymax)
        df = works[has_title & in_range].copy().reset_index(drop=True)
        embeddings = load_refined_embeddings()

        if len(embeddings) != len(df):
            raise RuntimeError("Embedding size mismatch")

        df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
        if core_only:
            core_mask = df["cited_by_count"] >= CITE_THRESHOLD
            core_indices = df.index[core_mask].values
            df = df.loc[core_mask].reset_index(drop=True)
            embeddings = embeddings[core_indices]

        km = KMeans(n_clusters=n_clusters, random_state=42, n_init=20)
        df["cluster"] = km.fit_predict(embeddings)

        bounds = []
        for lbl in period_labels:
            lo, hi = [int(x) for x in lbl.replace("–", "-").split("-")]
            bounds.append((lo, hi))

        def assign_period(yr):
            for lbl, (lo, hi) in zip(period_labels, bounds):
                if lo <= yr <= hi:
                    return lbl
            return period_labels[-1]

        df["period"] = df["year"].apply(assign_period)
        return df
    except Exception as e:
        log.info("  (skipping paper data: %s)", e)
        return None


def collect_top_papers(df, period_labels, n_clusters):
    """Collect top-3 most-cited papers per (period, cluster)."""
    top_papers = {}
    for period in period_labels:
        for c in range(n_clusters):
            cell = df[(df["period"] == period) & (df["cluster"] == c)]
            cell_sorted = cell.sort_values("cited_by_count", ascending=False).head(3)
            papers = []
            for _, row in cell_sorted.iterrows():
                author = str(row.get("first_author", "?"))
                if len(author) > 25:
                    author = author[:23] + "…"
                yr = int(row["year"]) if pd.notna(row["year"]) else "?"
                title = str(row.get("title", ""))
                if len(title) > 80:
                    title = title[:78] + "…"
                cites = int(row["cited_by_count"]) if pd.notna(row["cited_by_count"]) else 0
                papers.append(f"{author} ({yr}), {title} [{cites} cit.]")
            top_papers[(period, c)] = papers
    return top_papers


def render_html(alluvial_data, cluster_labels, period_stacks, top_papers, output_path):
    """Render the interactive HTML/SVG alluvial diagram."""
    import matplotlib.pyplot as plt

    period_labels = alluvial_data.index.tolist()
    n_periods = len(period_labels)
    n_clusters = len(alluvial_data.columns)

    # Palette and layout
    palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))
    x_positions = np.linspace(0, 0.62, n_periods)
    col_width = 0.04

    # SVG dimensions
    svg_w, svg_h = 1350, 675
    pad_l, pad_r, pad_t, pad_b = 75, 420, 82, 52
    chart_w = svg_w - pad_l - pad_r
    chart_h = svg_h - pad_t - pad_b

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

    last_stacks = period_stacks[period_labels[-1]]

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
                      f'font-family="sans-serif">')

    # Title
    total = int(alluvial_data.values.sum())
    svg_parts.append(f'<text x="{svg_w//2}" y="28" text-anchor="middle" font-size="16" font-weight="bold">'
                     f'Thematic recomposition of scholarship around climate finance, 1990\u20132024</text>')
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

    # Column bars (with tooltips)
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
            paper_lines = "<br>".join(
                html_mod.escape(p) for p in top_papers.get((period, c), ["(no papers)"])
            )
            cluster_name = html_mod.escape(cluster_labels.get(c, f"Cluster {c}"))
            tooltip_inner = (f'<b>{period} \u2014 {cluster_name}</b><br>'
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
<title>Fig 3 \u2013 Alluvial (interactive)</title>
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

    with open(output_path, "w") as f:
        f.write(html_content)
    log.info("Saved interactive version -> %s", output_path)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(description="Render interactive alluvial HTML")
    parser.add_argument("--core-only", action="store_true",
                        help="Use core-only variant of input tables")
    parser.add_argument("--censor-gap", type=int, default=0,
                        help="Load censor-gap variant (affects output name only)")
    args = parser.parse_args(extra)

    alluvial_data, cluster_labels, fig_name = load_data(args.core_only, args.censor_gap)
    period_stacks = compute_stacks(alluvial_data)

    df = load_paper_data(alluvial_data, cluster_labels, args.core_only)
    if df is not None:
        top_papers = collect_top_papers(
            df, alluvial_data.index.tolist(), len(alluvial_data.columns)
        )
    else:
        top_papers = {}

    render_html(alluvial_data, cluster_labels, period_stacks, top_papers, io_args.output)
    log.info("Done.")


if __name__ == "__main__":
    main()
