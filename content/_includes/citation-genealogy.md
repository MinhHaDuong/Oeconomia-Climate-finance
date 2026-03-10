## 8. Citation Genealogy

**Script:** `scripts/analyze_genealogy.py`

### Backbone selection

Papers from `refined_works.csv` with an abstract longer than 50 characters, a valid year in 1985--2025, and cited_by_count >= 50 form the backbone. Result: approximately 1,128 backbone papers.

### Three-band lineage assignment

Each backbone paper is assigned to one of three bands using two data sources:

1. **KMeans semantic clusters** (from `semantic_clusters.csv`): cluster 2 corresponds to CDM/projects/mechanism literature.
2. **Bimodality axis scores** (from `tab_pole_papers.csv`): papers with negative axis scores lean accountability; positive scores lean efficiency.

Assignment logic:
- If a paper belongs to KMeans cluster 2 (CDM), it is assigned to **Band 0: CDM / Kyoto heritage**.
- Otherwise, if its bimodality axis score < 0, it is assigned to **Band 1: Accountability pole**.
- Otherwise, it is assigned to **Band 2: Efficiency pole**.

### Citation DAG construction

Internal citation edges are extracted from `citations.csv`: an edge (A -> B) exists when cited paper A and citing paper B are both in the backbone. Edges are deduplicated.

### Layout

- **X-axis:** Publication year (normalized to [0, 1]).
- **Y-axis:** Lineage band. Bands are ordered by median year of their papers (foundational at top). Within each band, papers from the same year are jittered vertically for readability.
- **Node size:** Proportional to the square root of citation count (scaled by sqrt(cited_by_count / 200)).
- **Cross-lineage arcs:** The top 15 cross-lineage citation edges (ranked by combined citation count of source and target) are highlighted with Bezier arcs.

### Outputs

- `fig_genealogy.{png,pdf}` -- static figure
- `fig_genealogy.html` -- interactive HTML/SVG version with hover tooltips and DOI click-through
- `tab_lineages.csv` -- lineage assignments for all backbone papers
