"""Temporal analysis of the climate finance corpus.

Produces:
- figures/fig1_emergence.pdf: Publication timeline with COP event annotations
- tables/tab1_terms.csv: First appearance and growth of key concepts in abstracts
"""

import os
import re

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns

from utils import BASE_DIR, CATALOGS_DIR

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Load data ---
df = pd.read_csv(os.path.join(CATALOGS_DIR, "unified_works.csv"))
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df = df.dropna(subset=["year"])
df["year"] = df["year"].astype(int)
print(f"Loaded {len(df)} works with valid year (range {df['year'].min()}–{df['year'].max()})")

# ============================================================
# Figure 1: Publication emergence timeline (1990–2025)
# ============================================================

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

# Style
sns.set_style("whitegrid")
fig, ax = plt.subplots(figsize=(12, 5))

# Bar chart
bars = ax.bar(counts.index, counts.values, color="#4C72B0", alpha=0.85, width=0.8)

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
ax.set_ylabel("Number of publications", fontsize=11)
ax.set_title(
    'The emergence of "climate finance" in academic literature (1990–2025)',
    fontsize=13,
    pad=15,
)
ax.set_xlim(1989, 2026)
ax.xaxis.set_major_locator(ticker.MultipleLocator(5))
ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

# Add total count annotation
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
fig.savefig(os.path.join(FIGURES_DIR, "fig1_emergence.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig1_emergence.png"), dpi=150, bbox_inches="tight")
print(f"Saved Figure 1 → figures/fig1_emergence.pdf")
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
