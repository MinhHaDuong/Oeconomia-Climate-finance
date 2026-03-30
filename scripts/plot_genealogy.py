"""Static citation genealogy figure (matplotlib).

Reads:
  content/tables/tab_lineages.csv — backbone papers with positions
  data/catalogs/refined_citations.csv — for internal citation edges

Produces:
  content/figures/fig_genealogy.png (and .pdf unless --no-pdf)
"""

import argparse
import os

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgba
from matplotlib.path import Path
from utils import (
    BASE_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_periods,
    load_refined_citations,
    normalize_doi,
    save_figure,
)

log = get_logger("plot_genealogy")

matplotlib.rcParams["font.size"] = 8

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
PERIOD_COLORS = ["#f0f0f0", "#e8e8e8", "#f0f0f0", "#e8e8e8"]

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
            edges.add((r, s))  # cited → citing
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


def _draw_time_context(ax, year_min, year_max):
    """Draw period bands and COP event markers."""
    for i in range(len(PERIOD_BOUNDS) - 1):
        x0 = (PERIOD_BOUNDS[i] - year_min) / max(year_max - year_min, 1)
        x1 = (PERIOD_BOUNDS[i + 1] - year_min) / max(year_max - year_min, 1)
        ax.axvspan(x0, x1, alpha=0.15, color=PERIOD_COLORS[i], zorder=0)
        xmid = (x0 + x1) / 2
        ax.text(xmid, 1.02, PERIOD_LABELS[i], ha="center", va="bottom",
                fontsize=8, color="grey")

    for yr, label in COP_EVENTS.items():
        if year_min <= yr <= year_max:
            x = (yr - year_min) / max(year_max - year_min, 1)
            ax.axvline(x, color="grey", linestyle="--", alpha=0.3, linewidth=0.7)
            ax.text(x, 1.01, label, ha="center", va="bottom", fontsize=6,
                    color="grey", rotation=45)


def _score_cross_lineage(edges, lineage, doi_meta):
    """Score cross-lineage edges by combined citation count, return top 15."""
    cross_scored = []
    for s, t in edges:
        if s in lineage and t in lineage and lineage[s] != lineage[t]:
            score = (doi_meta.get(t, {}).get("cited_by_count", 0)
                     + doi_meta.get(s, {}).get("cited_by_count", 0))
            cross_scored.append((s, t, score))
    cross_scored.sort(key=lambda x: -x[2])
    return cross_scored[:15]


def _draw_edges(ax, edges, positions, lineage, doi_meta):
    """Draw citation edges and highlighted cross-lineage arcs."""
    for src, tgt in edges:
        if src not in positions or tgt not in positions:
            continue
        x0, y0 = positions[src]
        x1, y1 = positions[tgt]
        src_comm = lineage.get(src)
        tgt_comm = lineage.get(tgt)

        if src_comm == tgt_comm:
            color = BAND_COLORS_RGB.get(src_comm, "grey")
            alpha = 0.15
            style = "-"
        else:
            color = "grey"
            alpha = 0.08
            style = "--"

        ax.plot([x0, x1], [y0, y1], linestyle=style, color=color,
                alpha=alpha, linewidth=0.3, zorder=1)

    for s, t, _ in _score_cross_lineage(edges, lineage, doi_meta):
        if s not in positions or t not in positions:
            continue
        x0, y0 = positions[s]
        x1, y1 = positions[t]
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


def _draw_nodes_and_labels(ax, backbone_dois, doi_meta, lineage, positions, palette):
    """Draw scatter nodes and author-year labels for top 40 papers."""
    for d in backbone_dois:
        if d not in positions:
            continue
        x, y = positions[d]
        c = lineage[d]
        cit_count = doi_meta.get(d, {}).get("cited_by_count", 0)
        size = 10 + 60 * np.sqrt(max(cit_count, 0) / 200)
        ax.scatter(x, y, s=size, color=[palette[c]], alpha=0.8,
                   edgecolors="white", linewidths=0.3, zorder=3)

    top_papers = sorted(backbone_dois,
                        key=lambda d: doi_meta.get(d, {}).get("cited_by_count", 0),
                        reverse=True)[:40]

    for idx, d in enumerate(top_papers):
        if d not in positions:
            continue
        x, y = positions[d]
        meta = doi_meta.get(d, {})
        author = str(meta.get("first_author", ""))
        author = author.split(",")[0].split(";")[0].strip()
        if not author or author in ("nan", ""):
            continue
        yr = meta.get("year", "")
        if not yr or np.isnan(yr):
            continue

        label = f"{author} ({int(yr)})"
        offset_y = 0.012 if idx % 2 == 0 else -0.012

        ax.annotate(
            label, (x, y),
            xytext=(3, offset_y * 500),
            textcoords="offset points",
            fontsize=5.5, color="black", ha="left", va="center",
            path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            zorder=4,
        )


def render_figure(backbone_dois, doi_meta, lineage, positions, edges, no_pdf, output_path):
    """Render the static matplotlib genealogy figure."""
    palette = {c: to_rgba(BAND_COLORS_RGB[c]) for c in range(N_COMMUNITIES)}

    all_years = [doi_meta[d]["year"] for d in backbone_dois if doi_meta[d]["year"] is not None]
    year_min = min(all_years)
    year_max = max(all_years)

    band_height, comm_to_band, sorted_comms = _infer_bands(backbone_dois, lineage, positions)

    fig, ax = plt.subplots(figsize=(16, 10))

    _draw_time_context(ax, year_min, year_max)
    _draw_edges(ax, edges, positions, lineage, doi_meta)
    _draw_nodes_and_labels(ax, backbone_dois, doi_meta, lineage, positions, palette)

    # Legend: right-side labels aligned to lineage bands
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
        "Node size \u221d \u221acitations \u00b7 Cross-lineage arcs in red",
        fontsize=12, pad=20,
    )
    ax.axis("off")

    plt.tight_layout()
    fig_stem = os.path.splitext(output_path)[0]
    save_figure(fig, fig_stem, no_pdf=no_pdf)
    plt.close()
    log.info("Saved genealogy figure -> %s", output_path)


def main():
    parser = argparse.ArgumentParser(description="Render static genealogy figure")
    parser.add_argument("--output", default=os.path.join(FIGURES_DIR, "fig_genealogy.png"),
                        help="Output figure path")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF generation (PNG only)")
    parser.add_argument("--input", default=os.path.join(TABLES_DIR, "tab_lineages.csv"),
                        help="Input lineages table path")
    args = parser.parse_args()

    backbone_dois, doi_meta, lineage, positions = load_model(args.input)
    edges = load_edges(backbone_dois)
    render_figure(backbone_dois, doi_meta, lineage, positions, edges,
                  args.no_pdf, args.output)


if __name__ == "__main__":
    main()
