"""Semantic landscape of climate finance literature using multilingual embeddings.

Method:
- Embed titles, abstracts, and keywords with a multilingual sentence-transformer
- Incremental caching: only new works are encoded (keyed by DOI/source_id)
- UMAP dimensionality reduction to 2D
- KMeans clustering to identify discourse communities
- Cross-validate with co-citation communities (if available)

Produces:
- figures/fig_semantic.pdf: 2D semantic map colored by cluster
- figures/fig_semantic_lang.pdf: Same map colored by language
- data/catalogs/embeddings.npz: Embedding cache (vectors + metadata)
- data/catalogs/semantic_clusters.csv: Cluster assignments
"""

import argparse
import os
import warnings

# Suppress HuggingFace download/progress bars for clean nohup logs
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import pandas as pd

from utils import BASE_DIR, CATALOGS_DIR, EMBEDDINGS_PATH, normalize_doi, get_logger

log = get_logger("analyze_embeddings")

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Configuration ---
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TEXT_FIELDS = "title+abstract+keywords"
EMBEDDING_DIM = 384

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

CLUSTERS_PATH = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")


def build_text(row):
    """Concatenate title, abstract, and keywords for embedding."""
    parts = [str(row["title"])]
    abstract = row.get("abstract")
    if pd.notna(abstract) and len(str(abstract)) > 20:
        parts.append(str(abstract))
    keywords = row.get("keywords")
    if pd.notna(keywords):
        parts.append(str(keywords).replace(";", ", "))
    return ". ".join(parts)


def work_key(row):
    """Stable key for a work: DOI preferred, then source_id, then title hash."""
    if pd.notna(row["doi"]):
        return str(row["doi"])
    if pd.notna(row["source_id"]):
        return str(row["source_id"])
    import hashlib
    return "title:" + hashlib.md5(str(row["title"]).encode()).hexdigest()


def text_hash(text):
    """Short hash of the text that was embedded, to detect content changes."""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:8]



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works-input",
        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
        help="Works CSV to embed (default: unified_works.csv)",
    )
    args = parser.parse_args()

    # Defer heavy imports so --help works without corpus group installed
    import hdbscan  # noqa: F401
    import matplotlib.pyplot as plt
    import seaborn as sns
    import torch
    import umap
    from sentence_transformers import SentenceTransformer

    # --- Load data ---
    log.info("Loading works from %s...", args.works_input)
    works = pd.read_csv(args.works_input)

    # Filter: must have a title, year in range
    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
    df = works[has_title & in_range].copy().reset_index(drop=True)
    log.info("Works with titles (1990-2025): %d", len(df))

    # Build keys, text, and text hashes
    df["_key"] = df.apply(work_key, axis=1)
    df["_text"] = df.apply(build_text, axis=1)
    df["_thash"] = df["_text"].apply(text_hash)

    # --- Incremental embedding cache ---
    legacy_path = os.path.join(CATALOGS_DIR, "embeddings.npy")

    key_to_vec = {}   # key → vector
    key_to_hash = {}  # key → text hash (to detect content changes)
    if os.path.exists(EMBEDDINGS_PATH):
        cache = np.load(EMBEDDINGS_PATH, allow_pickle=True)
        cached_model = str(cache["model"]) if "model" in cache.files else ""
        cached_fields = str(cache["text_fields"]) if "text_fields" in cache.files else ""
        if cached_model == MODEL_NAME and cached_fields == TEXT_FIELDS:
            cached_keys = cache["keys"]
            cached_vecs = cache["vectors"]
            cached_hashes = cache["text_hashes"] if "text_hashes" in cache.files else None
            key_to_vec = dict(zip(cached_keys, cached_vecs))
            if cached_hashes is not None:
                key_to_hash = dict(zip(cached_keys, cached_hashes))
            log.info("Loaded %d cached embeddings (model: %s, fields: %s)",
                     len(key_to_vec), MODEL_NAME, TEXT_FIELDS)
        else:
            log.info("Config changed (model: %r→%r, fields: %r→%r), full recompute",
                     cached_model, MODEL_NAME, cached_fields, TEXT_FIELDS)
    elif os.path.exists(legacy_path):
        log.info("Found legacy %s, will migrate to .npz (full recompute)", legacy_path)
    else:
        log.info("No embedding cache found, full computation")

    # A cached entry is valid only if key exists AND text hash matches
    keys = df["_key"].values
    thashes = df["_thash"].values
    hit_mask = np.array([
        k in key_to_vec and key_to_hash.get(k) == h
        for k, h in zip(keys, thashes)
    ])
    n_cached = int(hit_mask.sum())
    n_new = len(df) - n_cached
    n_stale = sum(1 for k in keys if k in key_to_vec) - n_cached
    if n_stale > 0:
        log.info("Embeddings: %d cached, %d stale, %d new", n_cached, n_stale, n_new - n_stale)
    else:
        log.info("Embeddings: %d cached, %d to compute", n_cached, n_new)

    # Encode only new works
    if n_new > 0:
        n_cpu = os.cpu_count() or 4
        torch.set_num_threads(n_cpu)
        log.info("Loading %s (%d threads)...", MODEL_NAME, n_cpu)
        model = SentenceTransformer(MODEL_NAME)

        new_texts = df.loc[~hit_mask, "_text"].tolist()
        log.info("Encoding %d texts...", n_new)
        new_vecs = model.encode(
            new_texts,
            batch_size=256,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
    else:
        new_vecs = np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    # Assemble full array in df order
    embeddings = np.empty((len(df), EMBEDDING_DIM), dtype=np.float32)
    if n_cached > 0:
        embeddings[hit_mask] = np.array([key_to_vec[k] for k in keys[hit_mask]])
    if n_new > 0:
        embeddings[~hit_mask] = new_vecs

    # Save cache
    np.savez_compressed(
        EMBEDDINGS_PATH,
        vectors=embeddings,
        keys=keys,
        text_hashes=thashes,
        model=np.array(MODEL_NAME),
        text_fields=np.array(TEXT_FIELDS),
    )
    log.info("Saved %d embeddings → %s", len(embeddings), EMBEDDINGS_PATH)

    # Clean up legacy file
    if os.path.exists(legacy_path):
        os.remove(legacy_path)
        log.info("Removed legacy %s", legacy_path)

    log.info("Embedding shape: %s", embeddings.shape)


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
    # Step 2: HDBSCAN clustering
    # ============================================================

    log.info("Clustering with KMeans (k=6, matching co-citation communities)...")
    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=6, random_state=42, n_init=20)
    df["semantic_cluster"] = kmeans.fit_predict(coords)
    n_clusters = 6
    n_noise = 0
    log.info("Semantic clusters: %d", n_clusters)

    # Cluster sizes
    for c in sorted(df["semantic_cluster"].unique()):
        label = f"Cluster {c}" if c >= 0 else "Noise"
        log.info("  %s: %d", label, (df['semantic_cluster'] == c).sum())


    # ============================================================
    # Step 3: Characterize clusters
    # ============================================================

    # For each cluster, find most common keywords
    log.info("=== Cluster keyword profiles ===")
    for c in range(n_clusters):
        members = df[df["semantic_cluster"] == c]
        # Extract keywords
        all_kw = []
        for kw_str in members["keywords"].dropna():
            all_kw.extend([k.strip().lower() for k in str(kw_str).split(";")])
        from collections import Counter
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
        # Match by DOI
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

    sns.set_style("whitegrid")

    # --- Figure 3a: Colored by semantic cluster ---
    fig, ax = plt.subplots(figsize=(12, 9))

    # Plot clusters
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
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic.pdf"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic.png"), dpi=150, bbox_inches="tight")
    log.info("Saved semantic map → figures/fig_semantic.pdf")
    plt.close()


    # --- Figure 3b: Colored by language ---
    fig, ax = plt.subplots(figsize=(12, 9))

    lang_map = {"en": "English", "fr": "French", "zh": "Chinese",
                "ja": "Japanese", "de": "German", "es": "Spanish", "pt": "Portuguese"}
    df["lang_label"] = df["language"].map(lang_map).fillna("Other")

    lang_colors = {
        "English": "lightgrey",
        "French": "#E63946",
        "Chinese": "#E9C46A",
        "Japanese": "#264653",
        "German": "#2A9D8F",
        "Spanish": "#F4A261",
        "Portuguese": "#606C38",
        "Other": "#ADB5BD",
    }

    # Plot English first (background)
    en = df[df["lang_label"] == "English"]
    ax.scatter(en["umap_x"], en["umap_y"],
               c=lang_colors["English"], s=3, alpha=0.2, label=f"English (n={len(en)})")

    # Plot non-English on top
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
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_lang.pdf"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_lang.png"), dpi=150, bbox_inches="tight")
    log.info("Saved semantic map (language) → figures/fig_semantic_lang.pdf")
    plt.close()


    # --- Figure 3c: Colored by period ---
    fig, ax = plt.subplots(figsize=(12, 9))

    period_map = {
        (1990, 2008): "1990–2008",
        (2009, 2015): "2009–2015",
        (2016, 2021): "2016–2021",
        (2022, 2025): "2022–2025",
    }
    period_colors = {
        "1990–2008": "#ADB5BD",
        "2009–2015": "#F4A261",
        "2016–2021": "#E76F51",
        "2022–2025": "#264653",
    }

    def assign_period(year):
        for (lo, hi), label in period_map.items():
            if lo <= year <= hi:
                return label
        return "Other"

    df["period"] = df["year"].apply(assign_period)

    for period in ["1990–2008", "2009–2015", "2016–2021", "2022–2025"]:
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
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_period.pdf"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig_semantic_period.png"), dpi=150, bbox_inches="tight")
    log.info("Saved semantic map (period) → figures/fig_semantic_period.pdf")
    plt.close()


    # --- Save cluster assignments ---
    out = df[["source", "doi", "title", "first_author", "year", "language",
              "semantic_cluster", "umap_x", "umap_y"]].copy()
    out.to_csv(CLUSTERS_PATH, index=False)
    log.info("Saved cluster assignments → %s. Done.", CLUSTERS_PATH)


if __name__ == "__main__":
    main()
