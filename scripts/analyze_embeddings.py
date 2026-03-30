"""Semantic landscape analysis: UMAP projection + KMeans clustering.

Phase 2 analysis step: loads pre-computed embeddings.npz (from enrich_embeddings.py)
and produces UMAP projections, KMeans clusters, and visualization figures.

Method:
- Load embeddings.npz vectors and associated works metadata
- UMAP dimensionality reduction to 2D
- KMeans clustering to identify discourse communities
- Cross-validate with co-citation communities (if available)

Produces:
- data/catalogs/semantic_clusters.csv: Cluster assignments with UMAP coordinates
- figures/fig_semantic.pdf: 2D semantic map colored by cluster
- figures/fig_semantic_lang.pdf: Same map colored by language
- figures/fig_semantic_period.pdf: Same map colored by period
"""

import argparse
import os
import warnings
from collections import Counter

import numpy as np
import pandas as pd
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    EMBEDDINGS_PATH,
    get_logger,
    load_analysis_config,
    normalize_doi,
    work_key,
)

log = get_logger("analyze_embeddings")

warnings.filterwarnings("ignore", category=FutureWarning)

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

CLUSTERS_PATH = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")


def _generate_figures(df, n_clusters, plt, sns, pdf=False):
    """Generate semantic landscape figures (cluster, language, period)."""
    sns.set_style("whitegrid")

    # --- Figure: Colored by semantic cluster ---
    fig, ax = plt.subplots(figsize=(12, 9))
    palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))
    for c in range(n_clusters):
        members = df[df["semantic_cluster"] == c]
        ax.scatter(
            members["umap_x"], members["umap_y"],
            c=[palette[c]], s=8, alpha=0.5,
            label=f"Cluster {c} (n={len(members)})",
        )
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9, markerscale=3)
    ax.set_title(
        "Semantic landscape of climate finance literature\n"
        "(multilingual abstract embeddings, UMAP projection)",
        fontsize=13,
    )
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic.png"), dpi=150, bbox_inches="tight")
    if pdf:
        fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic.pdf"), dpi=300, bbox_inches="tight")
    log.info("Saved semantic map → figures/fig_semantic.png%s", " + .pdf" if pdf else "")
    plt.close()

    # --- Figure: Colored by language ---
    fig, ax = plt.subplots(figsize=(12, 9))
    lang_map = {"en": "English", "fr": "French", "zh": "Chinese",
                "ja": "Japanese", "de": "German", "es": "Spanish", "pt": "Portuguese"}
    df["lang_label"] = df["language"].map(lang_map).fillna("Other")
    lang_colors = {
        "English": "lightgrey", "French": "#E63946", "Chinese": "#E9C46A",
        "Japanese": "#264653", "German": "#2A9D8F", "Spanish": "#F4A261",
        "Portuguese": "#606C38", "Other": "#ADB5BD",
    }
    en = df[df["lang_label"] == "English"]
    ax.scatter(en["umap_x"], en["umap_y"],
               c=lang_colors["English"], s=3, alpha=0.2, label=f"English (n={len(en)})")
    for lang in ["French", "Chinese", "Japanese", "German", "Spanish", "Portuguese", "Other"]:
        subset = df[df["lang_label"] == lang]
        if len(subset) > 0:
            ax.scatter(
                subset["umap_x"], subset["umap_y"],
                c=lang_colors[lang], s=20, alpha=0.8,
                label=f"{lang} (n={len(subset)})",
                edgecolors="white", linewidths=0.3,
            )
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9, markerscale=2)
    ax.set_title(
        "Language distribution in the semantic landscape\n"
        "(non-English works highlighted)",
        fontsize=13,
    )
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_lang.png"), dpi=150, bbox_inches="tight")
    if pdf:
        fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_lang.pdf"), dpi=300, bbox_inches="tight")
    log.info("Saved semantic map (language) → figures/fig_semantic_lang.png%s", " + .pdf" if pdf else "")
    plt.close()

    # --- Figure: Colored by period ---
    fig, ax = plt.subplots(figsize=(12, 9))
    period_map = {
        (1990, 2008): "1990–2008",
        (2009, 2015): "2009–2015",
        (2016, 2021): "2016–2021",
        (2022, 2024): "2022–2024",
    }
    period_colors = {
        "1990–2008": "#ADB5BD",
        "2009–2015": "#F4A261",
        "2016–2021": "#E76F51",
        "2022–2024": "#264653",
    }

    def assign_period(year):
        for (lo, hi), label in period_map.items():
            if lo <= year <= hi:
                return label
        return "Other"

    df["period"] = df["year"].apply(assign_period)
    for period in ["1990–2008", "2009–2015", "2016–2021", "2022–2024"]:
        subset = df[df["period"] == period]
        ax.scatter(
            subset["umap_x"], subset["umap_y"],
            c=period_colors[period], s=5, alpha=0.4,
            label=f"{period} (n={len(subset)})",
        )
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9, markerscale=4)
    ax.set_title(
        "Temporal evolution of the semantic landscape\n"
        "(colored by article's periodization)",
        fontsize=13,
    )
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_period.png"), dpi=150, bbox_inches="tight")
    if pdf:
        fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_period.pdf"), dpi=300, bbox_inches="tight")
    log.info("Saved semantic map (period) → figures/fig_semantic_period.png%s", " + .pdf" if pdf else "")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works-input",
        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
        help="Works CSV with metadata (default: enriched_works.csv)",
    )
    parser.add_argument(
        "--embeddings-input",
        default=EMBEDDINGS_PATH,
        help="Embeddings .npz file (default: embeddings.npz)",
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF figures")
    args = parser.parse_args()

    # Defer heavy imports so --help works without analysis group installed
    import matplotlib.pyplot as plt
    import seaborn as sns
    import umap
    from sklearn.cluster import KMeans

    # --- Load works metadata ---
    log.info("Loading works from %s...", args.works_input)
    works = pd.read_csv(args.works_input)

    # Filter: must have a title, year in range (from config)
    _cfg = load_analysis_config()
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]
    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
    df = works[has_title & in_range].copy().reset_index(drop=True)
    log.info("Works with titles (%d-%d): %d", _year_min, _year_max, len(df))

    # --- Load pre-computed embeddings ---
    log.info("Loading embeddings from %s...", args.embeddings_input)
    cache = np.load(args.embeddings_input, allow_pickle=True)
    cached_keys = cache["keys"]
    cached_vecs = cache["vectors"]
    key_to_vec = dict(zip(cached_keys, cached_vecs))
    log.info("Loaded %d cached embeddings", len(key_to_vec))

    # Build keys and align embeddings to df order
    df["_key"] = df.apply(work_key, axis=1)
    dim = cached_vecs.shape[1]
    embeddings = np.zeros((len(df), dim), dtype=np.float32)
    n_matched = 0
    for i, key in enumerate(df["_key"]):
        if key in key_to_vec:
            embeddings[i] = key_to_vec[key]
            n_matched += 1
    log.info("Matched %d / %d works to embeddings", n_matched, len(df))
    n_unmatched = len(df) - n_matched
    if n_unmatched > 0:
        match_pct = 100 * n_matched / len(df)
        log.warning("%d works have no embedding (%.1f%% match rate) — "
                    "zero vectors will distort UMAP/clustering. "
                    "Re-run enrich_embeddings.py if this is unexpected.", n_unmatched, match_pct)

    # ============================================================
    # Step 1: UMAP dimensionality reduction
    # ============================================================

    log.info("Computing UMAP projection...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.05,
        metric="cosine",
        random_state=42,
        low_memory=True,
    )
    coords = reducer.fit_transform(embeddings)
    df["umap_x"] = coords[:, 0]
    df["umap_y"] = coords[:, 1]
    log.info("UMAP done: %s", coords.shape)

    # ============================================================
    # Step 2: KMeans clustering
    # ============================================================

    cfg = load_analysis_config()
    k = cfg["clustering"]["k"]
    log.info("Clustering with KMeans (k=%d from config/analysis.yaml)...", k)
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=20)
    df["semantic_cluster"] = kmeans.fit_predict(coords)
    n_clusters = k
    log.info("Semantic clusters: %d", n_clusters)

    # Cluster sizes
    for c in range(n_clusters):
        log.info("  Cluster %d: %d", c, (df['semantic_cluster'] == c).sum())

    # ============================================================
    # Step 3: Characterize clusters
    # ============================================================

    log.info("=== Cluster keyword profiles ===")
    for c in range(n_clusters):
        members = df[df["semantic_cluster"] == c]
        all_kw = []
        for kw_str in members["keywords"].dropna():
            all_kw.extend([k.strip().lower() for k in str(kw_str).split(";")])
        kw_counts = Counter(all_kw).most_common(10)
        kw_str = ", ".join(f"{k} ({n})" for k, n in kw_counts)
        median_year = int(members["year"].median())
        log.info("Cluster %d (n=%d, median year=%d): %s", c, len(members), median_year, kw_str)

    # ============================================================
    # Step 4: Cross-validate with co-citation communities
    # ============================================================

    cocit_path = os.path.join(CATALOGS_DIR, "communities.csv")
    if os.path.exists(cocit_path):
        log.info("=== Cross-validation with co-citation communities ===")
        cocit = pd.read_csv(cocit_path)
        df["doi_norm"] = df["doi"].apply(normalize_doi)
        cocit["doi_norm"] = cocit["doi"].apply(normalize_doi)

        merged = df.merge(cocit[["doi_norm", "community"]], on="doi_norm", how="inner")
        if len(merged) > 0:
            cross_tab = pd.crosstab(
                merged["semantic_cluster"],
                merged["community"],
                margins=True,
            )
            log.info("Matched %d works with both assignments:\n%s", len(merged), cross_tab)
        else:
            log.info("No DOI matches between semantic clusters and co-citation communities")

    # ============================================================
    # Step 5: Visualize
    # ============================================================

    _generate_figures(df, n_clusters, plt, sns, pdf=args.pdf)

    # --- Save cluster assignments ---
    out = df[["source", "doi", "title", "first_author", "year", "language",
              "semantic_cluster", "umap_x", "umap_y"]].copy()
    out.to_csv(CLUSTERS_PATH, index=False)
    log.info("Saved cluster assignments → %s. Done.", CLUSTERS_PATH)


if __name__ == "__main__":
    main()
