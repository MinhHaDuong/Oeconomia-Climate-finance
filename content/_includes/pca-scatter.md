## 7. PCA Scatter Plots

**Script:** `scripts/plot_fig45_pca_scatter.py`

This script visualizes how the field's thematic structure evolves over time by plotting individual papers in year × axis-score space.

### Supervised mode (`--supervised`)

Projects all papers onto the efficiency↔accountability seed axis (identical to Section 6's Method A axis). Produces a single-panel scatter plot:
- **X-axis:** publication year (with ±0.3 uniform jitter to reduce overplotting)
- **Y-axis:** seed axis score (positive = efficiency, negative = accountability)
- **Color:** three-period scheme (blue 1990–2006, orange 2007–2014, green 2015–2025)
- **Point size:** proportional to sqrt(cited_by_count / 50)
- **Black line:** yearly median score (smoother)
- **Vertical dashes:** COP events (Rio, Kyoto, Copenhagen, Paris, Glasgow, Baku)
- **Period bands:** light background shading for each period

Recommended with `--core-only` for the paper figure (`fig_seed_axis_core.png`), showing {{< var corpus_core >}} influential papers. The seed axis is bimodal in core (ΔBIC = {{< var bim_core_dbic_embedding >}}), and the yearly median reveals a drift from the accountability side toward efficiency over time.

### Unsupervised mode (default)

Runs PCA (10 components) on embeddings, tests each PC for bimodality (1- vs 2-component GMM), and plots one panel per PC with ΔBIC > 200. Each PC's poles are labelled using the top 3 TF-IDF terms correlated with positive and negative scores.

On full corpus ({{< var corpus_with_embeddings >}} papers), 3 PCs qualify:
| PC | Variance | ΔBIC | (+) pole | (−) pole |
|----|----------|------|----------|----------|
| PC2 | {{< var pca_emb_pc2_var_pct >}}% | {{< var pca_emb_pc2_dbic >}} | green, financial, sustainability | carbon, emissions, climate change |
| PC3 | 4.1% | 390 | land, forest, biomass | agreement, paris, finance |
| PC4 | {{< var pca_emb_pc4_var_pct >}}% | {{< var pca_emb_pc4_dbic >}} | cdm, clean development | finance, green, financial |

On core ({{< var corpus_core >}} papers), no PC passes ΔBIC > 200. Unsupervised bimodality requires the full corpus's breadth to emerge.

### Outputs

- `fig_seed_axis_core.png` -- supervised axis, core papers (paper figure)
- `fig_pca_scatter.png` -- unsupervised 3-panel, full corpus (appendix)
- `tab_seed_axis_core.csv` -- seed axis metadata (variance, ΔBIC, pole terms)
- `tab_pca_components.csv` -- unsupervised PC metadata
