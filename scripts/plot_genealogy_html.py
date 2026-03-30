"""Interactive HTML citation genealogy with hover tooltips and DOI links.

Reads:
  content/tables/tab_lineages.csv — backbone papers with positions
  data/catalogs/refined_citations.csv — for internal citation edges

Produces:
  content/figures/fig_genealogy.html — interactive SVG with reference popups
"""

import argparse
import html as html_mod
import os

import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba
from utils import (
    BASE_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_periods,
    load_refined_citations,
    normalize_doi,
)

log = get_logger("plot_genealogy_html")

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

# --- Config ---
_cfg = load_analysis_config()
_period_tuples, PERIOD_LABELS = load_analysis_periods()
PERIOD_BOUNDS = (
    [_cfg["periodization"]["year_min"]]
    + _cfg["periodization"]["breaks"]
    + [_cfg["periodization"]["year_max"] + 1]
)

COP_EVENTS = {
    1992: "Rio",
    1997: "Kyoto",
    2009: "Copenhagen",
    2015: "Paris",
    2021: "Glasgow",
    2024: "Baku",
}

# Band scheme (must match analyze_genealogy.py)
BAND_COLORS_RGB = {0: "#F4A261", 1: "#457B9D", 2: "#E63946"}
COMMUNITY_NAMES = {0: "CDM / Kyoto heritage", 1: "Accountability pole", 2: "Efficiency pole"}
N_COMMUNITIES = 3

# SVG coordinate system
SVG_W, SVG_H = 1400, 900
PAD_L, PAD_R, PAD_T, PAD_B = 60, 320, 70, 45
CHART_W = SVG_W - PAD_L - PAD_R
CHART_H = SVG_H - PAD_T - PAD_B


def _to_sx(xnorm):
    return PAD_L + xnorm * CHART_W


def _to_sy(ynorm):
    return PAD_T + CHART_H - ynorm * CHART_H


def load_model(lineages_path):
    """Load tab_lineages.csv and build the data structures the renderer needs."""
    df = pd.read_csv(lineages_path)

    doi_meta = {}
    lineage = {}
    positions = {}
    backbone_dois = set()

    for _, row in df.iterrows():
        d = row["doi"]
        backbone_dois.add(d)
        lineage[d] = int(row["lineage"])
        positions[d] = (float(row["x"]), float(row["y"]))
        doi_meta[d] = {
            "title": str(row.get("title", "") or ""),
            "first_author": str(row.get("first_author", "") or ""),
            "year": row["year"] if pd.notna(row["year"]) else None,
            "cited_by_count": row.get("cited_by_count", 0),
        }

    return backbone_dois, doi_meta, lineage, positions


def load_edges(backbone_dois):
    """Load citation edges between backbone papers."""
    cit = load_refined_citations()
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)

    edges = set()
    for _, row in cit.iterrows():
        s = row["source_doi"]
        r = row["ref_doi"]
        if s in backbone_dois and r in backbone_dois:
            edges.add((r, s))
    return list(edges)


def _infer_bands(backbone_dois, lineage, positions):
    """Infer band ordering from y-coordinates in precomputed positions."""
    band_height = 1.0 / max(N_COMMUNITIES, 1)
    comm_to_band = {}
    for c in range(N_COMMUNITIES):
        ys = [positions[d][1] for d in backbone_dois if lineage.get(d) == c and d in positions]
        if ys:
            comm_to_band[c] = round(np.median(ys) / band_height - 0.5)
    sorted_comms = sorted(comm_to_band.keys(), key=lambda c: comm_to_band[c])
    return band_height, comm_to_band, sorted_comms


def _svg_header(n_backbone):
    """SVG opening, background, and title."""
    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
                 f'font-family="sans-serif">')
    parts.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="white"/>')
    parts.append(f'<text x="{SVG_W//2}" y="25" text-anchor="middle" font-size="15" font-weight="bold">'
                 f'Citation genealogy of climate finance scholarship ({n_backbone} most-cited papers)</text>')
    parts.append(f'<text x="{SVG_W//2}" y="45" text-anchor="middle" font-size="11" fill="#666">'
                 f'Node size \u221d \u221acitations \u00b7 Hover for full reference \u00b7 Click to open DOI</text>')
    return parts


def _svg_time_context(year_min, year_max):
    """Period bands, COP markers, and year axis ticks."""
    parts = []
    for i in range(len(PERIOD_BOUNDS) - 1):
        x0 = _to_sx((PERIOD_BOUNDS[i] - year_min) / max(year_max - year_min, 1))
        x1 = _to_sx((PERIOD_BOUNDS[i + 1] - year_min) / max(year_max - year_min, 1))
        fill = "#f5f5f5" if i % 2 == 0 else "#ececec"
        parts.append(f'<rect x="{x0:.1f}" y="{PAD_T}" width="{x1-x0:.1f}" '
                     f'height="{CHART_H}" fill="{fill}"/>')
        xmid = (x0 + x1) / 2
        parts.append(f'<text x="{xmid:.1f}" y="{PAD_T - 5}" text-anchor="middle" '
                     f'font-size="10" fill="#888">{PERIOD_LABELS[i]}</text>')

    for yr, label in COP_EVENTS.items():
        if year_min <= yr <= year_max:
            x = _to_sx((yr - year_min) / max(year_max - year_min, 1))
            parts.append(f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{PAD_T + CHART_H}" '
                         f'stroke="#bbb" stroke-width="0.7" stroke-dasharray="4,3"/>')
            parts.append(f'<text x="{x:.1f}" y="{PAD_T - 15}" text-anchor="middle" '
                         f'font-size="8" fill="#999" transform="rotate(-30,{x:.1f},{PAD_T - 15})">'
                         f'{label}</text>')

    year_ticks = list(range(int(year_min) - int(year_min) % 5, int(year_max) + 5, 5))
    for yr in year_ticks:
        xn = (yr - year_min) / max(year_max - year_min, 1)
        if 0 <= xn <= 1:
            x = _to_sx(xn)
            parts.append(f'<text x="{x:.1f}" y="{PAD_T + CHART_H + 18}" text-anchor="middle" '
                         f'font-size="9" fill="#888">{yr}</text>')
    return parts


def _svg_edges(edges, positions, lineage, doi_meta):
    """Within-lineage edges and top 15 cross-lineage arcs."""
    palette_hex = {c: BAND_COLORS_RGB[c] for c in range(N_COMMUNITIES)}
    parts = []

    for src, tgt in edges:
        if src not in positions or tgt not in positions:
            continue
        src_c = lineage.get(src)
        tgt_c = lineage.get(tgt)
        if src_c != tgt_c:
            continue
        x0, y0 = positions[src]
        x1, y1 = positions[tgt]
        sx0, sy0 = _to_sx(x0), _to_sy(y0)
        sx1, sy1 = _to_sx(x1), _to_sy(y1)
        parts.append(f'<line x1="{sx0:.1f}" y1="{sy0:.1f}" x2="{sx1:.1f}" y2="{sy1:.1f}" '
                     f'stroke="{palette_hex[src_c]}" stroke-width="0.3" opacity="0.15"/>')

    # Top 15 cross-lineage arcs
    cross_scored = []
    for s, t in edges:
        if s in lineage and t in lineage and lineage[s] != lineage[t]:
            score = (doi_meta.get(t, {}).get("cited_by_count", 0)
                     + doi_meta.get(s, {}).get("cited_by_count", 0))
            cross_scored.append((s, t, score))
    cross_scored.sort(key=lambda x: -x[2])

    for s, t, _ in cross_scored[:15]:
        if s not in positions or t not in positions:
            continue
        sx0, sy0 = _to_sx(positions[s][0]), _to_sy(positions[s][1])
        sx1, sy1 = _to_sx(positions[t][0]), _to_sy(positions[t][1])
        scx = (sx0 + sx1) / 2
        scy = (sy0 + sy1) / 2 + 30 * (1 if sy0 > sy1 else -1)
        parts.append(f'<path d="M{sx0:.1f},{sy0:.1f} Q{scx:.1f},{scy:.1f} {sx1:.1f},{sy1:.1f}" '
                     f'fill="none" stroke="#E63946" stroke-width="0.8" opacity="0.4" '
                     f'stroke-dasharray="3,2"/>')
    return parts


def _svg_nodes(backbone_dois, doi_meta, lineage, positions, popup_dois, palette):
    """SVG circles for all backbone papers, with tooltips for popup DOIs."""
    def rgba_svg(c_idx, alpha=0.8):
        r, g, b, _ = palette[c_idx]
        return f"rgba({int(r*255)},{int(g*255)},{int(b*255)},{alpha})"

    parts = []
    sorted_backbone = sorted(backbone_dois, key=lambda d: d in popup_dois)
    for d in sorted_backbone:
        if d not in positions:
            continue
        x, y = positions[d]
        sx, sy = _to_sx(x), _to_sy(y)
        c = lineage[d]
        cit_count = doi_meta.get(d, {}).get("cited_by_count", 0)
        radius = 3 + 8 * np.sqrt(max(cit_count, 0) / 200)

        if d in popup_dois:
            meta = doi_meta.get(d, {})
            author = html_mod.escape(str(meta.get("first_author", "?")))
            title = html_mod.escape(str(meta.get("title", "")))
            yr = int(meta["year"]) if meta.get("year") and not np.isnan(meta["year"]) else "?"
            doi_str = html_mod.escape(str(d))
            doi_url = f"https://doi.org/{d}" if d and d not in ("nan", "none", "") else ""
            tooltip = (f"<b>{author} ({yr})</b><br>"
                       f"<i>{title}</i><br>"
                       f"{int(cit_count)} citations<br>"
                       f"<span style='color:#888;font-size:10px'>{doi_str}</span>")
            tooltip_attr = tooltip.replace('"', '&quot;')
            doi_attr = html_mod.escape(doi_url, quote=True)
            parts.append(
                f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius:.1f}" '
                f'fill="{rgba_svg(c, 0.8)}" stroke="white" stroke-width="0.5" '
                f'class="node" data-tooltip="{tooltip_attr}" data-doi="{doi_attr}" '
                f'style="cursor:pointer"/>')
        else:
            parts.append(
                f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{radius:.1f}" '
                f'fill="{rgba_svg(c, 0.15)}" stroke="none"/>')
    return parts


def _svg_labels(top_papers, doi_meta, positions):
    """Author-year text labels for the most-cited papers."""
    parts = []
    for idx, d in enumerate(top_papers):
        if d not in positions:
            continue
        x, y = positions[d]
        sx, sy = _to_sx(x), _to_sy(y)
        meta = doi_meta.get(d, {})
        author = str(meta.get("first_author", ""))
        author = author.split(",")[0].split(";")[0].strip()
        if not author or author in ("nan", ""):
            continue
        yr = meta.get("year", "")
        if not yr or np.isnan(yr):
            continue
        label = html_mod.escape(f"{author} ({int(yr)})")
        offset_y = -12 if idx % 2 == 0 else 12
        parts.append(
            f'<text x="{sx + 4:.1f}" y="{sy + offset_y:.1f}" font-size="7.5" '
            f'fill="black" pointer-events="none">'
            f'<tspan stroke="white" stroke-width="2.5" paint-order="stroke">{label}</tspan></text>')
    return parts


def _svg_legend(backbone_dois, lineage, palette, band_height, comm_to_band, sorted_comms):
    """Right-side lineage band labels."""
    legend_x = PAD_L + CHART_W + 15
    parts = []
    for c in sorted_comms:
        band = comm_to_band[c]
        band_center_y = _to_sy((band + 0.5) * band_height)
        name = COMMUNITY_NAMES.get(c, f"Cluster {c}")
        label_lines = name.split(" / ")
        n = sum(1 for d in backbone_dois if lineage.get(d) == c)
        label_lines.append(f"(n={n})")
        line_h = 15
        start_y = band_center_y - (len(label_lines) - 1) * line_h / 2
        pr, pg, pb, _ = palette[c]
        dark = f"rgb({int(pr*255*0.6)},{int(pg*255*0.6)},{int(pb*255*0.6)})"
        for li, line in enumerate(label_lines):
            fill = dark if li < len(label_lines) - 1 else "#888"
            fsize = "11" if li < len(label_lines) - 1 else "9"
            parts.append(
                f'<text x="{legend_x}" y="{start_y + li * line_h:.1f}" '
                f'font-size="{fsize}" fill="{fill}" dominant-baseline="central">'
                f'{html_mod.escape(line)}</text>')
    return parts


_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Fig 4 \u2013 Citation genealogy (interactive)</title>
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
{svg_content}
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


def render_html(backbone_dois, doi_meta, lineage, positions, edges, output_path):
    """Render interactive SVG+JS genealogy figure."""
    palette = {c: to_rgba(BAND_COLORS_RGB[c]) for c in range(N_COMMUNITIES)}

    all_years = [doi_meta[d]["year"] for d in backbone_dois if doi_meta[d]["year"] is not None]
    year_min = min(all_years)
    year_max = max(all_years)

    band_height, comm_to_band, sorted_comms = _infer_bands(backbone_dois, lineage, positions)

    top_papers = sorted(backbone_dois,
                        key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0),
                        reverse=True)[:40]
    popup_dois = set(sorted(backbone_dois,
                            key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0),
                            reverse=True)[:100])
    popup_dois.update(top_papers)

    svg = []
    svg.extend(_svg_header(len(backbone_dois)))
    svg.extend(_svg_time_context(year_min, year_max))
    svg.extend(_svg_edges(edges, positions, lineage, doi_meta))
    svg.extend(_svg_nodes(backbone_dois, doi_meta, lineage, positions, popup_dois, palette))
    svg.extend(_svg_labels(top_papers, doi_meta, positions))
    svg.extend(_svg_legend(backbone_dois, lineage, palette, band_height, comm_to_band, sorted_comms))
    svg.append('</svg>')

    html_content = _HTML_TEMPLATE.format(svg_content=''.join(svg))

    with open(output_path, "w") as f:
        f.write(html_content)
    log.info("Saved interactive genealogy -> %s", output_path)


def main():
    parser = argparse.ArgumentParser(description="Render interactive genealogy HTML")
    parser.add_argument("--output", default=os.path.join(FIGURES_DIR, "fig_genealogy.html"),
                        help="Output HTML path")
    parser.add_argument("--input", default=os.path.join(TABLES_DIR, "tab_lineages.csv"),
                        help="Input lineages table path")
    args = parser.parse_args()

    backbone_dois, doi_meta, lineage, positions = load_model(args.input)
    edges = load_edges(backbone_dois)
    render_html(backbone_dois, doi_meta, lineage, positions, edges, args.output)


if __name__ == "__main__":
    main()
