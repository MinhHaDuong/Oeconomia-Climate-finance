"""Temporal analysis of the climate finance corpus.

Produces:
- figures/fig1_emergence.pdf: Three economics series on common timeline
  (economics in OpenAlex, climate-in-economics, climate finance corpus)
- tables/tab1_terms.csv: First appearance and growth of key concepts in abstracts
"""

import argparse
import json
import os
import re

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import seaborn as sns

from utils import BASE_DIR, CATALOGS_DIR, MAILTO, polite_get, save_figure

parser = argparse.ArgumentParser(description="Temporal analysis (Fig 1)")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

BASELINES_PATH = os.path.join(CATALOGS_DIR, "openalex_economics_baselines.json")

# --- Load corpus data ---
df = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df = df.dropna(subset=["year"])
df["year"] = df["year"].astype(int)
print(f"Loaded {len(df)} works with valid year (range {df['year'].min()}–{df['year'].max()})")

# Filter to relevant period
mask = (df["year"] >= 1990) & (df["year"] <= 2025)
df_period = df[mask]
counts = df_period.groupby("year").size().reindex(range(1990, 2026), fill_value=0)

# Key events for annotation
events = {
    1992: "Rio\nUNFCCC",
    1997: "Kyoto",
    2009: "Copenhagen\n$100bn pledge",
    2010: "Cancún\nGCF created",
    2015: "Paris\nAgreement",
    2021: "Glasgow",
    2024: "Baku\nNCQG $300bn",
}

# Three-act period bands
PERIOD_BOUNDS = [1990, 2007, 2015, 2026]
PERIOD_LABELS = ["I. Before\nclimate finance", "II. Crystallization", "III. Established field"]
PERIOD_COLORS = ["#f0f0f0", "#e8e0f0", "#f0e8e0"]


# ============================================================
# Fetch OpenAlex economics baselines (cached)
# ============================================================

def fetch_openalex_economics_baselines():
    """Fetch two series from OpenAlex:
    1. Economics publications by year (concept Economics, level 0)
    2. Climate-in-economics: Economics + "climate" in title
    """
    if os.path.exists(BASELINES_PATH):
        with open(BASELINES_PATH) as f:
            cached = json.load(f)
        print(f"Loaded cached economics baselines from {BASELINES_PATH}")
        return cached

    print("Fetching economics baselines from OpenAlex API...")

    # Economics concept ID in OpenAlex
    # C162324750 = Economics (level 0)
    economics_concept = "C162324750"

    # Series 1: All economics publications by year
    economics_by_year = {}
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"concept.id:{economics_concept},publication_year:1990-2025",
        "group_by": "publication_year",
        "mailto": MAILTO,
    }
    resp = polite_get(url, params=params, delay=1.0)
    data = resp.json()
    for item in data.get("group_by", []):
        yr = int(item["key"])
        economics_by_year[yr] = item["count"]
    print(f"  Economics publications: {len(economics_by_year)} years")

    # Series 2: Climate-in-economics (economics + "climate" in title)
    climate_econ_by_year = {}
    params2 = {
        "filter": f"concept.id:{economics_concept},title.search:climate,publication_year:1990-2025",
        "group_by": "publication_year",
        "mailto": MAILTO,
    }
    resp2 = polite_get(url, params=params2, delay=1.0)
    data2 = resp2.json()
    for item in data2.get("group_by", []):
        yr = int(item["key"])
        climate_econ_by_year[yr] = item["count"]
    print(f"  Climate-in-economics: {len(climate_econ_by_year)} years")

    result = {
        "economics": {str(k): v for k, v in economics_by_year.items()},
        "climate_economics": {str(k): v for k, v in climate_econ_by_year.items()},
    }

    os.makedirs(os.path.dirname(BASELINES_PATH), exist_ok=True)
    with open(BASELINES_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  Cached → {BASELINES_PATH}")
    return result


baselines = fetch_openalex_economics_baselines()
economics = {int(k): v for k, v in baselines["economics"].items()}
climate_econ = {int(k): v for k, v in baselines["climate_economics"].items()}


# ============================================================
# Figure 1: Three economics series on common timeline
# ============================================================

sns.set_style("whitegrid")
fig, ax = plt.subplots(figsize=(12, 5.5))

years = list(range(1990, 2026))

# Build series
econ_raw = np.array([economics.get(yr, 0) for yr in years], dtype=float)
clim_econ_raw = np.array([climate_econ.get(yr, 0) for yr in years], dtype=float)
cf_raw = np.array([counts.get(yr, 0) for yr in years], dtype=float)

# Period background bands
for i in range(len(PERIOD_BOUNDS) - 1):
    ax.axvspan(PERIOD_BOUNDS[i] - 0.5, PERIOD_BOUNDS[i + 1] - 0.5,
               alpha=0.3, color=PERIOD_COLORS[i], zorder=0)
    mid = (PERIOD_BOUNDS[i] + PERIOD_BOUNDS[i + 1]) / 2
    ax.text(mid, ax.get_ylim()[1] if i > 0 else 0, PERIOD_LABELS[i],
            ha="center", va="top", fontsize=7.5, color="grey", alpha=0.7,
            transform=ax.get_xaxis_transform())

# Secondary y-axis for the two OpenAlex series (much larger numbers)
ax2 = ax.twinx()

# Plot economics series on ax2 (right y-axis)
ax2.plot(years, econ_raw, color="#E07B39", linewidth=2, linestyle="--",
         alpha=0.8, label="Economics (OpenAlex)", zorder=2)
ax2.plot(years, clim_econ_raw, color="#55A868", linewidth=2, linestyle="-.",
         alpha=0.8, label='"Climate" in economics (OpenAlex)', zorder=2)

# Plot climate finance corpus on ax (left y-axis) as bars
bars = ax.bar(years, cf_raw, color="#4C72B0", alpha=0.85, width=0.8,
              label="Climate finance corpus", zorder=3)

# Annotate events
for yr, label in events.items():
    yval = counts.get(yr, 0)
    ax.annotate(
        label,
        xy=(yr, yval),
        xytext=(0, 25),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=7.5,
        arrowprops=dict(arrowstyle="-", color="grey", lw=0.8),
        bbox=dict(boxstyle="round,pad=0.2", fc="lightyellow", ec="grey", lw=0.5),
    )

ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("Climate finance publications", fontsize=11)
ax2.set_ylabel("OpenAlex publications", fontsize=10, color="grey")
ax2.tick_params(axis="y", labelcolor="grey", labelsize=9)
ax2.spines["right"].set_color("grey")
ax2.spines["right"].set_alpha(0.5)

ax.set_title(
    "The emergence of climate finance in economics (1990–2025)",
    fontsize=13,
    pad=15,
)
ax.set_xlim(1989, 2026)
ax.xaxis.set_major_locator(ticker.MultipleLocator(5))
ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

# Period labels at top
for i in range(len(PERIOD_BOUNDS) - 1):
    mid = (PERIOD_BOUNDS[i] + PERIOD_BOUNDS[i + 1]) / 2
    ax.text(mid, 1.02, PERIOD_LABELS[i],
            ha="center", va="bottom", fontsize=7.5, color="grey", alpha=0.8,
            transform=ax.get_xaxis_transform())

# Combined legend
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left",
          fontsize=8.5, framealpha=0.9)

# Total count annotation
total = counts.sum()
ax.text(
    0.98, 0.95,
    f"N = {total:,} publications",
    transform=ax.transAxes,
    ha="right", va="top",
    fontsize=10,
    bbox=dict(boxstyle="round", fc="white", ec="grey", alpha=0.8),
)

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, "fig1_emergence"), no_pdf=args.no_pdf)
plt.close()


# ============================================================
# Table 1: Key concept emergence in abstracts
# ============================================================

# Works with abstracts
df_abs = df_period.dropna(subset=["abstract"]).copy()
df_abs["abstract_lower"] = df_abs["abstract"].str.lower()
print(f"Works with abstracts in 1990–2025: {len(df_abs)}")

# Key terms to track (regex patterns for precision)
terms = {
    # Efficiency / leverage vocabulary
    "climate finance": r"climate\s+financ",
    "Rio marker": r"rio\s+marker",
    "leverage": r"\bleverage\b",
    "crowding-in": r"crowd(?:ing[\s-]*in|[\s-]*in)",
    "de-risking": r"de[\s-]*risk",
    "mobilised private finance": r"mobili[sz]ed?\s+(?:private\s+)?financ",
    "blended finance": r"blended\s+financ",
    # Accountability / equity vocabulary
    "additionality": r"\badditionality\b",
    "grant-equivalent": r"grant[\s-]*equivalent",
    "over-reporting": r"over[\s-]*report",
    "accountability": r"\baccountability\b",
    "climate justice": r"climate\s+justice",
    "loss and damage": r"loss\s+and\s+damage",
    # Institutional terms
    "Standing Committee on Finance": r"standing\s+committee\s+on\s+financ",
    "Green Climate Fund": r"green\s+climate\s+fund",
    "NCQG": r"\bncqg\b|new\s+collective\s+quantified\s+goal",
}

rows = []
for term_label, pattern in terms.items():
    matches = df_abs[df_abs["abstract_lower"].str.contains(pattern, regex=True, na=False)]
    if len(matches) == 0:
        rows.append({
            "term": term_label,
            "first_year": None,
            "total_mentions": 0,
            "peak_year": None,
            "peak_count": 0,
        })
        continue

    by_year = matches.groupby("year").size()
    first_year = int(by_year.index.min())
    peak_year = int(by_year.idxmax())
    peak_count = int(by_year.max())

    rows.append({
        "term": term_label,
        "first_year": first_year,
        "total_mentions": len(matches),
        "peak_year": peak_year,
        "peak_count": peak_count,
    })

tab1 = pd.DataFrame(rows).sort_values("first_year")
tab1.to_csv(os.path.join(TABLES_DIR, "tab1_terms.csv"), index=False)
print(f"\nSaved Table 1 → tables/tab1_terms.csv")
print(tab1.to_string(index=False))


# ============================================================
# Bonus: Language distribution over time
# ============================================================

df_lang = df_period.copy()
df_lang["lang_group"] = df_lang["language"].fillna("unknown").apply(
    lambda x: x if x in ("en", "fr", "zh", "ja", "de", "es", "pt") else "other"
)
lang_by_year = df_lang.groupby(["year", "lang_group"]).size().unstack(fill_value=0)
lang_by_year.to_csv(os.path.join(TABLES_DIR, "language_by_year.csv"))
print(f"\nSaved language distribution → tables/language_by_year.csv")

# Summary
print("\nLanguage distribution (all years):")
print(df_lang["lang_group"].value_counts())
