# NCC Figure Captions

Draft captions for the four figures of the Nature Climate Change Analysis piece.
Each caption should be under 300 words (NCC requirement).

## Figure 1: Structural divergence in scholarship around climate finance

Sliding-window Jensen-Shannon divergence of embedding distributions across
consecutive time periods, showing when the semantic structure of the
literature shifted. The baseline analysis (blue, k=0) detects multiple
candidate breakpoints. When transition years are censored (red, k=2),
only the 2009 peak survives, coinciding with the Copenhagen COP15 and
the emergence of "climate finance" as a consolidated field category.
The z-score measures how far each year's divergence departs from the
series mean; values above 2.0 (dashed line) indicate breaks at the 5%
significance level. Window size w=3 years; N=28,015 papers with
embeddings. Data: six bibliographic sources merged and de-duplicated
(OpenAlex, Semantic Scholar, ISTEX, bibCNRS, SciSpace, grey literature).

## Figure 2: Full corpus vs. core subset structural breaks

**a**, Full corpus (N=28,015): JS divergence z-scores across three
window sizes (w=2, 3, 4 years). Multiple breakpoints detected,
with the strongest at 2007 and 2013.
**b**, Core subset (papers cited 50 or more times, N=2,648): no
z-score exceeds the significance threshold. The absence of structural
breaks in the most-cited literature suggests that the semantic
reorganization detected in the full corpus was driven by the proliferation
of peripheral works rather than by shifts in the field's intellectual core.

## Figure 3: Bimodality along the efficiency-accountability axis

**a**, Kernel density estimate of axis scores across all papers, with
two-component Gaussian Mixture Model overlay (dashed lines). The
positive delta-BIC confirms bimodality. **b--d**, Period-decomposed
KDEs: the distribution is unimodal before 2007, begins separating
during 2007--2014, and is clearly bimodal after 2015. Axis scores
derived from cosine similarity to seed terms ("efficiency" vs.
"accountability") in 1024-dimensional sentence embeddings. The
post-2015 bimodality indicates that the field crystallized around
two competing framings of climate finance: one oriented toward
economic efficiency and private capital mobilization, the other
toward accountability and public obligation.

## Figure 4: Thematic stability across three periods

Alluvial diagram of thematic cluster membership across the three
data-derived periods (pre-2007, 2007--2014, post-2015). Band widths
are proportional to the number of publications in each cluster per
period. Cluster labels derived from top TF-IDF terms in each group.
The stable proportional structure across periods shows that while the
field grew rapidly, its thematic composition remained largely fixed
after the initial crystallization. Core shares (percentage of
highly-cited papers within each cluster) are noted where available.
Clustering: K-means (k=6) on sentence embeddings; cluster assignments
validated by lexical and keyword-based alternatives.
