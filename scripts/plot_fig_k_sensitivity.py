"""K-sensitivity figure: structural break persistence across cluster counts.

Reads:  tab_k_sensitivity.csv
Writes: fig_k_sensitivity.png (and .pdf unless --no-pdf)

Flags: --no-pdf

Run compute_breakpoints.py --robustness first to generate tab_k_sensitivity.csv.
"""

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd
from plot_style import COP_EVENTS
from utils import BASE_DIR, get_logger, save_figure

log = get_logger("plot_fig_k_sensitivity")

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

K_DEFAULT = 6

# --- Args ---
parser = argparse.ArgumentParser(description="Plot k-sensitivity figure")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()

# --- Load data ---
k_path = os.path.join(TABLES_DIR, "tab_k_sensitivity.csv")
if not os.path.exists(k_path):
    raise FileNotFoundError(
        f"Missing {k_path}. Run: uv run python scripts/compute_breakpoints.py --robustness"
    )
k_df = pd.read_csv(k_path)
k_values = [int(col.replace("js_k", "")) for col in k_df.columns if col.startswith("js_k")]

# --- Plot ---
fig, ax = plt.subplots(figsize=(12, 5))
k_colors = {4: "#E63946", 5: "#F4A261", 6: "#457B9D", 7: "#2A9D8F"}
for k in k_values:
    col = f"js_k{k}"
    valid = k_df[["year", col]].dropna()
    ax.plot(valid["year"], valid[col], "-o", color=k_colors.get(k, "grey"), markersize=4,
            label=f"k={k}", alpha=0.8, linewidth=1.5 if k == K_DEFAULT else 1.0)

for yr in COP_EVENTS.keys():
    if 2004 <= yr <= 2024:
        ax.axvline(yr, color="grey", linestyle="--", alpha=0.4, linewidth=0.8)

ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("JS divergence (w=3)", fontsize=11)
ax.set_title("K-sensitivity: do structural breaks persist across cluster counts?",
             fontsize=12, pad=15)
ax.legend(fontsize=9, framealpha=0.9)
plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, "fig_k_sensitivity"), no_pdf=args.no_pdf)
plt.close()
log.info("Saved fig_k_sensitivity.png")
