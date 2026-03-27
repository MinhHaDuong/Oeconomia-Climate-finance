# WARNING: AI-generated, not human-reviewed
"""UNFCCC-guided topic taxonomy analysis of the climate finance literature.

Hypothesis: the academic climate finance literature mirrors the organizational structure
of UNFCCC negotiations. Topic categories are defined by UNFCCC negotiation track keywords.

Steps:
1. Load refined_works.csv and filter to year in [1990,2024] with non-empty title
2. Classify each work by scanning title + abstract + keywords against 8 UNFCCC topics
3. Report topic distribution and unclassified count
4. Load refined_embeddings.npz and compute ARI vs KMeans k=6 and k=8
5. Report confusion matrix: UNFCCC topic × KMeans cluster
6. Compute silhouette in semantic, lexical (TF-IDF 100D SVD), and citation spaces
7. Track topic proportions over time (per-year percentage)
8. Save assignments to content/tables/tab_unfccc_topics.csv
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import normalize
from utils import BASE_DIR, get_logger, load_analysis_corpus

log = get_logger("analyze_unfccc_topics")

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*KMeans.*")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
OUTPUT_CSV = os.path.join(TABLES_DIR, "tab_unfccc_topics.csv")

# ---------------------------------------------------------------------------
# UNFCCC negotiation track keyword definitions
# ---------------------------------------------------------------------------

UNFCCC_TOPICS: dict[str, list[str]] = {
    "CDM_carbon_markets": [
        "clean development mechanism", "cdm", "joint implementation", " ji ",
        "emissions trading", "carbon market", "carbon offset", "cap and trade",
        " ets ", "allowance",
    ],
    "adaptation": [
        "adaptation", "adaptive capacity", "vulnerability", "resilience",
        "climate risk", "adaptation fund",
    ],
    "mitigation_finance": [
        "mitigation", " redd", "renewable energy", "energy transition",
        "low-carbon", "decarbonization", "abatement",
    ],
    "green_finance": [
        "green bond", " esg ", "sustainable finance", "climate risk",
        "stranded asset", "climate-related financial", " tcfd ", "disclosure",
    ],
    "development_finance": [
        "development", " oda ", " aid ", "developing countr", "least developed",
        " sids ", "capacity building", "north-south", "north south", "equity",
    ],
    "loss_and_damage": [
        "loss and damage", "warsaw mechanism", "non-economic loss",
        "slow onset", "irreversible",
    ],
    "governance": [
        "governance", "accountability", "transparency", " mrv ", "reporting",
        "paris agreement", " unfccc", " cop ", "compliance",
    ],
    "GCF_funds": [
        "green climate fund", " gcf ", " gef ", "global environment facilit",
        "adaptation fund", "multilateral fund", "climate fund",
    ],
}

TOPIC_NAMES = list(UNFCCC_TOPICS.keys())


def make_searchable(row: pd.Series) -> str:
    """Concatenate title + abstract + keywords into a single lowercase string."""
    parts = []
    for col in ("title", "abstract", "keywords"):
        val = row.get(col, "")
        if pd.notna(val) and str(val).strip():
            parts.append(str(val).lower())
    return " " + " ".join(parts) + " "


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    """Count how many distinct keywords from the list appear in text."""
    hits = 0
    for kw in keywords:
        if kw.lower() in text:
            hits += 1
    return hits


def classify_work(text: str) -> tuple[str | None, str | None, dict[str, int]]:
    """Assign primary (and optional secondary) UNFCCC topic to a work.

    Returns (primary_topic, secondary_topic | None, scores_dict).
    Secondary topic is assigned only when the runner-up score equals the top score
    (tie) or is at least 2 hits and within 1 of the top score.
    """
    scores = {topic: count_keyword_hits(text, kws)
              for topic, kws in UNFCCC_TOPICS.items()}
    sorted_topics = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_name, top_score = sorted_topics[0]
    second_name, second_score = sorted_topics[1]

    if top_score == 0:
        return None, None, scores

    primary = top_name
    secondary = None
    # Multi-label: assign secondary if runner-up is within 1 hit and has ≥ 2 hits
    if second_score >= 2 and (top_score - second_score) <= 1:
        secondary = second_name

    return primary, secondary, scores


# ---------------------------------------------------------------------------
# Citation-graph distance matrix (sparse co-citation proxy)
# ---------------------------------------------------------------------------

def build_citation_cooccurrence(df: pd.DataFrame, max_works: int = 10000) -> np.ndarray | None:
    """Build a sparse co-occurrence matrix from refined_citations.csv.

    Returns an (n_works, n_works) float32 array or None if citations unavailable.
    Only uses shared-citation overlap as a proxy for citation-space proximity.
    Limited to max_works for memory reasons.
    """
    from utils import CATALOGS_DIR
    citations_path = os.path.join(CATALOGS_DIR, "refined_citations.csv")
    if not os.path.exists(citations_path):
        log.warning("refined_citations.csv not found — skipping citation silhouette")
        return None

    log.info("Loading refined_citations.csv for citation-space silhouette …")
    # refined_citations.csv columns: source_doi, source_id, ref_doi, ref_title, ...
    cit = pd.read_csv(citations_path, usecols=["source_id", "ref_doi"],
                      low_memory=False)

    # Index works present in df
    n = min(len(df), max_works)
    work_ids = df["source_id"].iloc[:n].tolist()
    id_to_idx = {sid: i for i, sid in enumerate(work_ids)}

    # Build outgoing citation sets
    cit_sub = cit[cit["source_id"].isin(id_to_idx)]
    from collections import defaultdict
    out_citations: dict[str, set] = defaultdict(set)
    for _, row in cit_sub.iterrows():
        # Use ref_doi as the cited work identifier
        if pd.notna(row["ref_doi"]) and row["ref_doi"]:
            out_citations[row["source_id"]].add(row["ref_doi"])

    # Sparse co-citation: Jaccard similarity on outgoing citation sets
    # For silhouette, use 1 - Jaccard as distance proxy
    # We compute a dense matrix for the subset
    log.info("Building %d × %d citation Jaccard matrix (may be slow) …", n, n)
    mat = np.zeros((n, n), dtype=np.float32)
    ids_list = work_ids
    for i, sid_i in enumerate(ids_list):
        set_i = out_citations.get(sid_i, set())
        if not set_i:
            continue
        for j in range(i + 1, n):
            sid_j = ids_list[j]
            set_j = out_citations.get(sid_j, set())
            if not set_j:
                continue
            union = set_i | set_j
            inter = set_i & set_j
            if union:
                sim = len(inter) / len(union)
                mat[i, j] = sim
                mat[j, i] = sim
    # Distance = 1 - similarity; ensure diagonal is exactly zero
    dist = 1.0 - mat
    np.fill_diagonal(dist, 0.0)
    return dist


def compute_silhouette_scores(
    df, embeddings, classified_mask, topic_to_int, rng, *, skip_citation=False
):
    """Compute silhouette scores in semantic, lexical, and citation spaces."""
    log.info("=== SILHOUETTE SCORES OF UNFCCC TOPIC ASSIGNMENTS ===")

    MAX_SILHOUETTE = 10000
    sil_mask = classified_mask.values
    sil_df = df[sil_mask].copy()
    sil_emb = embeddings[sil_mask]
    sil_labels = sil_df["unfccc_topic"].map(topic_to_int).values

    if len(sil_df) > MAX_SILHOUETTE:
        rng_idx = rng.choice(len(sil_df), MAX_SILHOUETTE, replace=False)
        sil_emb_sample = sil_emb[rng_idx]
        sil_labels_sample = sil_labels[rng_idx]
        log.info("Silhouette sample: %d works (from %d classified)", MAX_SILHOUETTE, len(sil_df))
    else:
        rng_idx = None
        sil_emb_sample = sil_emb
        sil_labels_sample = sil_labels

    # Semantic space
    log.info("Computing silhouette in semantic (embedding) space …")
    sil_semantic = silhouette_score(sil_emb_sample, sil_labels_sample, metric="cosine")
    log.info("Semantic (embedding cosine):  silhouette = %.4f", sil_semantic)

    # Lexical space (TF-IDF 100D SVD)
    log.info("Computing TF-IDF representation for lexical silhouette …")
    texts_for_tfidf = sil_df["title"].fillna("") + " " + sil_df["abstract"].fillna("") + " " + sil_df["keywords"].fillna("")
    if rng_idx is not None:
        texts_sample = texts_for_tfidf.iloc[rng_idx].values
    else:
        texts_sample = texts_for_tfidf.values

    tfidf = TfidfVectorizer(max_features=20000, stop_words="english",
                            sublinear_tf=True, min_df=3)
    tfidf_mat = tfidf.fit_transform(texts_sample)
    svd = TruncatedSVD(n_components=100, random_state=42)
    lex_vecs = svd.fit_transform(tfidf_mat)
    lex_vecs_norm = normalize(lex_vecs, norm="l2")
    sil_lexical = silhouette_score(lex_vecs_norm, sil_labels_sample, metric="cosine")
    log.info("Lexical (TF-IDF 100D SVD cosine):  silhouette = %.4f", sil_lexical)

    # Citation space
    if skip_citation:
        log.info("Skipping citation-space silhouette (--skip-citation-silhouette flag)")
    else:
        MAX_CIT = 3000
        log.info("Building citation co-occurrence matrix (up to %d works) …", MAX_CIT)
        cit_df_slice = sil_df.iloc[:MAX_CIT].reset_index(drop=True)
        cit_labels_slice = sil_labels[:MAX_CIT]
        dist_mat = build_citation_cooccurrence(cit_df_slice, max_works=MAX_CIT)
        if dist_mat is not None:
            unique_labels = np.unique(cit_labels_slice)
            if len(unique_labels) >= 2:
                sil_citation = silhouette_score(dist_mat, cit_labels_slice, metric="precomputed")
                log.info("Citation (co-citation Jaccard distance):  silhouette = %.4f", sil_citation)
            else:
                log.info("Citation space:  silhouette = N/A (only one label class in sample)")
        else:
            log.info("Citation space:  silhouette = N/A (no citations data)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="UNFCCC-guided topic taxonomy analysis of climate finance literature"
    )
    parser.add_argument(
        "--no-pdf", action="store_true",
        help="No-op (no figures generated here)"
    )
    parser.add_argument(
        "--skip-citation-silhouette", action="store_true",
        help="Skip the expensive citation-space silhouette computation"
    )
    args = parser.parse_args()

    os.makedirs(TABLES_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load corpus with embeddings
    # ------------------------------------------------------------------
    log.info("Loading analysis corpus (year 1990–2024, non-empty title) …")
    df, embeddings = load_analysis_corpus(with_embeddings=True)
    log.info("Corpus loaded: %d works, embeddings shape %s", len(df), embeddings.shape)

    # ------------------------------------------------------------------
    # 2. Classify each work by UNFCCC topic
    # ------------------------------------------------------------------
    log.info("Classifying works by UNFCCC negotiation track …")
    searchable = df.apply(make_searchable, axis=1)

    primary_topics: list[str | None] = []
    secondary_topics: list[str | None] = []
    for text in searchable:
        prim, sec, _ = classify_work(text)
        primary_topics.append(prim)
        secondary_topics.append(sec)

    df["unfccc_topic"] = primary_topics
    df["unfccc_secondary"] = secondary_topics

    # ------------------------------------------------------------------
    # 3. Report: topic distribution and unclassified count
    # ------------------------------------------------------------------
    log.info("=== UNFCCC TOPIC CLASSIFICATION RESULTS ===")

    n_unclassified = df["unfccc_topic"].isna().sum()
    n_classified = len(df) - n_unclassified

    log.info("Total works analyzed: %d", len(df))
    log.info("Classified: %d (%.1f%%)", n_classified, 100 * n_classified / len(df))
    log.info("Unclassified: %d (%.1f%%)", n_unclassified, 100 * n_unclassified / len(df))
    log.info("Works per UNFCCC topic:")
    for topic in TOPIC_NAMES:
        count = (df["unfccc_topic"] == topic).sum()
        pct = 100 * count / len(df)
        log.info("  %-30s  %5d  (%.1f%%)", topic, count, pct)
    log.info("  %-30s  %5d  (%.1f%%)", "unclassified", n_unclassified, 100 * n_unclassified / len(df))

    multi_label_count = df["unfccc_secondary"].notna().sum()
    log.info("Multi-label works (top-2 close): %d (%.1f%%)", multi_label_count, 100 * multi_label_count / len(df))

    # ------------------------------------------------------------------
    # 4 & 5. ARI: UNFCCC labels vs KMeans k=6, k=8
    # ------------------------------------------------------------------
    log.info("=== ADJUSTED RAND INDEX: UNFCCC TOPICS vs KMeans CLUSTERING ===")

    # Only evaluate on classified works
    classified_mask = df["unfccc_topic"].notna()
    emb_classified = embeddings[classified_mask]
    df_classified = df[classified_mask].copy()

    # Numeric label encoding for ARI
    topic_to_int = {t: i for i, t in enumerate(TOPIC_NAMES)}
    true_labels = df_classified["unfccc_topic"].map(topic_to_int).values

    rng = np.random.RandomState(42)

    for k in (6, 8):
        log.info("Running KMeans k=%d on embeddings …", k)
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km_labels = km.fit_predict(emb_classified)
        ari = adjusted_rand_score(true_labels, km_labels)
        log.info("KMeans k=%d  ARI = %.4f", k, ari)

        # Confusion matrix: UNFCCC topic (rows) × KMeans cluster (cols)
        log.info("Confusion matrix: UNFCCC topic × KMeans cluster (k=%d)", k)
        conf = pd.crosstab(
            df_classified["unfccc_topic"],
            km_labels,
            rownames=["UNFCCC topic"],
            colnames=[f"KMeans(k={k})"],
        )
        conf = conf.reindex(TOPIC_NAMES, fill_value=0)
        log.info("\n%s", conf.to_string())

    # ------------------------------------------------------------------
    # 6. Silhouette scores in semantic, lexical, and citation spaces
    # ------------------------------------------------------------------
    compute_silhouette_scores(
        df, embeddings, classified_mask, topic_to_int, rng,
        skip_citation=args.skip_citation_silhouette,
    )

    # ------------------------------------------------------------------
    # 7. Topic proportions over time (per-year %)
    # ------------------------------------------------------------------
    log.info("=== UNFCCC TOPIC PROPORTIONS OVER TIME (per-year %%) ===")

    df_time = df[df["year"].between(1992, 2024)].copy()
    df_time["year"] = df_time["year"].astype(int)

    # Pivot: rows=year, cols=topic
    topic_year = df_time.groupby(["year", "unfccc_topic"]).size().unstack(fill_value=0)
    topic_year_pct = topic_year.div(topic_year.sum(axis=1), axis=0) * 100

    # Log only topics with >1% average share
    avg_shares = topic_year_pct.mean()
    notable_topics = avg_shares[avg_shares > 1].index.tolist()
    display_cols = [t for t in TOPIC_NAMES if t in topic_year_pct.columns and t in notable_topics]

    log.info("%6s" + "".join(" %15s" % t[:14] for t in display_cols), "Year")
    for year, row in topic_year_pct[display_cols].iterrows():
        log.info("%6d" + "".join(" %14.1f%%" % row[t] for t in display_cols), year)

    # Summary: major trend lines
    log.info("Topic with highest share per 5-year epoch:")
    for epoch_start in range(1990, 2025, 5):
        epoch_end = min(epoch_start + 4, 2024)
        mask = df_time["year"].between(epoch_start, epoch_end)
        sub = df_time[mask]["unfccc_topic"].value_counts()
        if len(sub) > 0 and sub.iloc[0] > 0:
            top_t = sub.index[0]
            top_pct = 100 * sub.iloc[0] / mask.sum()
            log.info("  %d–%d: %s (%.1f%%)", epoch_start, epoch_end, top_t, top_pct)

    # ------------------------------------------------------------------
    # 8. Save topic assignments CSV
    # ------------------------------------------------------------------
    out_cols = ["doi", "source_id", "title", "year", "unfccc_topic"]
    out_df = df[out_cols].copy()
    out_df.to_csv(OUTPUT_CSV, index=False)
    log.info("Saved topic assignments → %s", OUTPUT_CSV)
    log.info("Rows: %d (all filtered works, with NaN where unclassified)", len(out_df))


if __name__ == "__main__":
    main()
