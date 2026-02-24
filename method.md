# Climate Finance corpus analysis plan

Ha Duong Minh, 2026-02-24

## Claude Plan

### Context

The article for Oeconomia argues climate finance became an economic object through a periodization currently imposed from COP milestones (1990-2008, 2009-2015, 2015-2021, 2021-2025). We replace 2 of 3 figures with visualizations that test this periodization empirically and show intellectual community dynamics:

Keep Fig 1 (bar chart): publication timeline -- unique info on field volume
Replace Fig 2 (static co-citation network) with alluvial diagram -- community flows across data-derived periods, with breakpoint detection testing the COP-based periodization
Replace Fig 3 (UMAP scatter) with citation genealogy -- time-ordered citation DAG showing intellectual communities, not inferred ancestry
No LLM, no API calls. Uses only existing data. Two new scripts.

*Methodological novelty claim*

We introduce endogenous structural break detection in intellectual fields using embedding drift and clustering instability.

To our knowledge, this specific combination has not been used to periodize an intellectual field in HET/STS: sentence embeddings + sliding-window Jensen-Shannon divergence on cluster distributions + robustness testing across parameters → data-driven periodization of a scholarly field.

Closest precedents (all partial):

Goutsmedt et al. (Oeconomia special issue, 2021): computational approaches to economics -- citation networks, not embeddings
Coccia (2018): LDA topic modeling of Journal of Economic History -- bag-of-words, no structural break detection
Vilhena et al. (Scientometrics 2023): functional data analysis of word frequencies in psychology -- no embeddings, no JS divergence
Embedding drift detection exists in ML monitoring (MMD, KS tests) but has never been applied to periodize an intellectual field
The article should state this clearly in the methods section and frame it as a contribution to digital HET methodology, citing Goutsmedt's call for computational approaches.

### Script 1: scripts/analyze_alluvial.py (new Fig 2)
Replaces: analyze_embeddings.py output (fig3_semantic*.pdf)
Output: figures/fig2_alluvial.pdf, figures/fig2_breakpoints.pdf, tables/tab2_alluvial.csv, tables/tab2_breakpoints.csv

*What it shows*

Two sub-figures:

Fig 2a (breakpoints): A time series showing when the intellectual structure of the field actually shifts. X-axis = year, Y-axis = structural dissimilarity between adjacent year cohorts. Peaks = detected breakpoints. COP milestones shown as vertical lines for comparison.

Fig 2b (alluvial): A flow diagram using the data-derived periods (not COP-based). Vertical bands = intellectual communities, width proportional to paper count. Flows show restructuring across empirically detected breaks.

*Why this matters*

The article's periodization (1990-2008, 2009-2015, 2015-2021, 2021-2025) is imposed from COP milestones, not derived from the literature. This script tests that periodization by detecting structural breaks endogenously. The comparison between detected breaks and COP dates is itself a finding.

*Method*

Load unified_works.csv + embeddings.npy (cached, 9,653 works)

Global clustering (done once, not per window):

Fit KMeans (k=6) on the full 9,653-embedding matrix
Each paper gets a fixed cluster assignment. This avoids re-fitting noise.
Mandatory alignment check: Compute Adjusted Rand Index between KMeans labels and Louvain community labels on the intersection of papers present in both communities.csv and the embedded corpus. Report n = |intersection| explicitly (many top-cited refs are outside the corpus; this coverage gap must be acknowledged).
Interpret ARI by rule-of-thumb categories (not a hard threshold):
ARI < 0.2: weak alignment -- the two capture different dimensions (semantic content vs. citation behavior). Both figures show complementary structure. State this explicitly.
ARI 0.2–0.5: moderate alignment -- broad correspondence with notable divergences.
ARI > 0.5: strong alignment -- embedding-based and citation-based community structure converge.
Structural break detection (sliding window):

Start at 2005 (not before -- early years too sparse for meaningful detection, treated as single formative phase)
For each year Y (2005-2023):
"Before" window: papers in [Y-w, Y], "After" window: papers in [Y+1, Y+1+w]
Two complementary metrics (both reported, no switching after the fact):
JS divergence between cluster membership proportion vectors of the two windows (normalized by total count per window). Captures structural redistribution across communities.
Cosine distance between mean embedding centroids of the two windows. Captures semantic drift independent of cluster assignments.
Volume confound check: Compute Pearson correlation between each metric's time series and the yearly publication count growth rate (year-over-year % change). Report r and p-value for both. If |r| > 0.5 for either metric, flag that it may partly track scale effects.
Minimum window size guard: require at least n_min = 30 papers per window. If a window has fewer, set JS(Y) = NA and skip that year. This prevents spurious divergence from sparse early data.
Robustness: Run with window sizes w = 2, 3, 4.
Breakpoint detection algorithm (reproducible, no visual judgment):
For each window size w, compute the JS divergence time series JS_w(Y) for Y in [2005, 2023]
Z-score normalize each series: z_w(Y) = (JS_w(Y) - mean) / std
Identify candidate breakpoints as local maxima of z_w(Y) with z_w(Y) > 1.5 (local maximum = z_w(Y) > z_w(Y-1) and z_w(Y) > z_w(Y+1))
Repeat steps 1-3 independently for the cosine distance time series
A robust breakpoint is a year that appears as candidate in >=2 of 3 window sizes within ±1 year on either metric (JS or cosine), and ideally both. Flag breakpoints supported by both metrics as "strongly robust", by one as "moderately robust". (i.e., if w=2 peaks at 2014 and w=3 peaks at 2015, that counts as one robust breakpoint at the year with higher mean z-score)
Select top 3 robust breakpoints by mean z-score across window sizes → these define period boundaries. Prefer strongly robust ones.
Output: tables/tab2_breakpoints.csv (year, JS_div_w2, JS_div_w3, JS_div_w4, z_w2, z_w3, z_w4, cosine_dist_w2, ...)
Output: tables/tab2_breakpoint_robustness.csv (candidate breakpoints per window size, robust flag, mean z-score)
Render: figures/fig2_breakpoints.pdf -- line plot of z-scored JS divergence (3 window sizes overlaid) with COP events as vertical lines, robust breakpoints marked with vertical bands
Segment into data-derived periods using the top 3 robust breakpoints (giving 4 periods). Pre-2005 is always the first period ("formative phase"), regardless of detection.

Per-period cluster distributions: Using the global KMeans assignments (step 2), compute the cluster membership distribution for each data-derived period. No re-clustering needed -- just count how many papers per cluster per period.

Render alluvial: matplotlib flow diagram with curved ribbons. Stream width = paper count per cluster per period. Flows connect the same global cluster across periods (no Hungarian matching needed since clusters are globally defined).

*Key data*

Approximate (exact sizes depend on detected breaks):

~9,653 papers with embeddings (1990-2025)
Pre-2007: very sparse (~50 papers), may need to be treated as single undifferentiated band

*Dependencies*

All already installed: numpy, pandas, scikit-learn (KMeans, adjusted_rand_score), scipy (linear_sum_assignment, cosine distance), matplotlib, seaborn

*Reuse from existing code*

Embedding loading pattern: from analyze_embeddings.py lines 42-80
Imports from utils.py: BASE_DIR, CATALOGS_DIR, normalize_doi
Color palette: plt.cm.Set2
Style: sns.set_style("whitegrid")
COP event list: from analyze_temporal.py (for overlay on breakpoints plot)

*Structure (~300 lines)*

```python
# Load data + embeddings (reuse pattern from analyze_embeddings.py)
# Step 1: Global KMeans clustering (k=6, full corpus, fit once)
# Step 2: Sliding-window JS divergence (w=2,3,4), cosine distance secondary
#   - Skip years before 2005
#   - Detect robust breakpoints (stable across >=2 window sizes)
#   - Plot JS divergence with COP overlay
#   - Save breakpoint + robustness tables
# Step 3: Segment into data-derived periods (pre-2005 = formative phase)
# Step 4: Compute per-period cluster distributions (no re-clustering)
# Step 5: Label communities from top keywords
# Step 6: Draw alluvial figure (flows = same global cluster across periods)
# Step 7: Save tables
```

### Script 2: scripts/analyze_genealogy.py (new Fig 3)

Replaces: analyze_cocitation.py output (fig2_communities.pdf)
Output: figures/fig3_genealogy.pdf, figures/fig3_genealogy.png, tables/tab3_lineages.csv
Generates 3 variants: --nodes 50, --nodes 200, --nodes 500 (default 200)

*What it shows*

A time-ordered citation genealogy of intellectual communities (not a phylogeny -- we visualize citation DAG constrained by community structure, not inferred ancestry):

X-axis = year (1990-2025), with period bands + COP event markers
Y-axis = lineage band (intellectual tradition)
Nodes = individual papers, size proportional to sqrt(citations)
Branches = Bezier curves connecting papers within a lineage
Cross-lineage arcs = dashed lines showing horizontal transfer (cross-community citations)
~40 anchor papers get text labels (Author, Year)

*Method*

Select backbone based on --nodes argument:

50: top 50 by citation count among the 200 community papers (subset, same labels)
200: the 200 papers already in communities.csv (co-citation analysis)
500: all papers with cited_by_count >= 20 and abstracts
Assign lineages -- same ontology for all variants, based on Louvain communities:

200-node: use existing community assignments from communities.csv
50-node: select top-cited within each community, keep their community labels
500-node: for papers not in the 200, assign to nearest Louvain community centroid in embedding space (compute mean embedding per community from the 200, then assign each extra paper to nearest centroid by cosine similarity). Threshold: if max cosine similarity to any centroid < 0.4, mark as "peripheral" instead of forcing into a lineage. Peripheral papers are rendered with reduced alpha (0.3) in their nearest lineage band, or collected in a separate thin "peripheral" band at the edge of the figure.
This ensures all variants use the same lineage ontology. Only density changes. Weakly related papers are not forced into strong lineages.

Build citation DAG: From citations.csv, filter to internal links (both source and ref DOI in backbone). Directed edges from cited (older) to citing (newer).

Layout:

X = publication year (continuous)
Y = lineage band. Order bands by median year of earliest papers (foundational lineages at top/bottom, recent ones in middle). Within a band, jitter papers vertically if they share a year.
Draw branch "spines" as cubic Bezier curves through the temporal centroid of each lineage per 5-year window.
Cross-lineage arcs: Identify top 15 citation links between papers in different lineages. Draw as thin dashed arcs.

Labels: Top ~40 papers by citation count get Author (Year) labels with smart placement (adjustText library, or manual offset).

Period background: Light grey bands for 4 periods + vertical dashed lines for COP events (same as analyze_temporal.py).

*Key data sources*

data/catalogs/communities.csv -- 200 papers with community assignments (for 200-node version)
data/catalogs/citations.csv -- for citation DAG and cross-lineage arcs
data/catalogs/unified_works.csv -- for metadata (year, cited_by_count, author)
data/catalogs/embeddings.npy + semantic_clusters.csv -- for 500-node version clustering

*Dependencies*

All already installed: numpy, pandas, networkx, scipy (hierarchy, interpolate), matplotlib (patches, patheffects). May want adjustText for label placement -- check if installed, otherwise manual offsets.

*Reuse from existing code*

Citation loading + DOI normalization: from analyze_cocitation.py lines 34-66
Community data loading: from analyze_cocitation.py lines 186-200
Node sizing (sqrt scale): from analyze_cocitation.py lines 239-240
Color palette: plt.cm.Set2
COP event annotations: from analyze_temporal.py (event list + vertical line drawing)
Imports from utils.py: BASE_DIR, CATALOGS_DIR, normalize_doi
Structure (~350 lines)

```python
# Parse --nodes argument (argparse, default=200)
# Load data (works, citations, communities, embeddings)
# Select backbone papers
# Assign lineages (Louvain communities, consistent across all variants)
# Build internal citation DAG
# Compute layout (x=year, y=lineage band)
# Draw period bands + COP markers
# Draw branch spines (Bezier curves)
# Draw nodes (scatter, sized by citations)
# Draw cross-lineage arcs (top 15)
# Draw labels (top ~40 papers)
# Save figure + lineage table
```

*File changes summary*

Action	File	Purpose
Create	scripts/analyze_alluvial.py	New Fig 2: alluvial community flows
Create	scripts/analyze_genealogy.py	New Fig 3: genealogical network
Keep	scripts/analyze_temporal.py	Fig 1: unchanged
Keep	scripts/analyze_cocitation.py	Still needed (generates communities.csv input)
Keep	scripts/analyze_embeddings.py	Still needed (generates embeddings.npy input)

Output files:

figures/fig2_breakpoints.{pdf,png} -- structural break detection vs COP milestones
figures/fig2_alluvial.{pdf,png} -- community flows across data-derived periods
figures/fig3_genealogy.{pdf,png} -- genealogical network (default 200 nodes)
figures/fig3_genealogy_50.{pdf,png} -- 50-node variant
figures/fig3_genealogy_500.{pdf,png} -- 500-node variant
tables/tab2_breakpoints.csv -- yearly JS divergence + cosine distance for w=2,3,4
tables/tab2_breakpoint_robustness.csv -- top breakpoints per window size, stability flags
tables/tab2_k_sensitivity.csv -- JS divergence curves for k=4,5,6,7
tables/tab2_alluvial.csv -- period-community paper counts and flows
tables/tab3_lineages.csv -- lineage assignments for backbone papers
tables/tab3_louvain_sensitivity.csv -- community assignments at γ=0.5,1.0,1.5,2.0

### Robustness appendices

Four sensitivity analyses, all produced by analyze_alluvial.py. Cheap to compute (minutes), high return for reviewers.

R1: Window size sensitivity (w = 2, 3, 4)
Already in the main analysis. The breakpoint robustness table reports:

Top 5 breakpoints per window size
Stability flag: "robust" if a year appears as top breakpoint in >=2 of 3 window sizes
Output: tables/tab2_breakpoint_robustness.csv
R2: k sensitivity in global clustering (k = 4, 5, 6, 7)
Re-run the full pipeline (global KMeans → JS divergence → breakpoint detection) for k = 4, 5, 6, 7
Report: do the same break years emerge regardless of k?
If top 2-3 breakpoints persist across k values → structural robustness demonstrated
Output: tables/tab2_k_sensitivity.csv (columns: year, JS_div_k4, JS_div_k5, JS_div_k6, JS_div_k7)
Render: overlay plot of JS divergence curves for different k values
R3: Louvain resolution parameter sensitivity (when supported)
For the genealogy figure (Script 2), re-run community detection with resolution parameter γ = 0.5, 1.0 (default), 1.5, 2.0
Library check: python-louvain (community package) supports resolution parameter. If unavailable or unsupported, try igraph's Leiden algorithm as fallback. If neither supports γ, log warning and skip R3.
Report: do the same major communities persist? Do key papers stay together?
Output: tables/tab3_louvain_sensitivity.csv (doi, community_γ05, community_γ10, community_γ15, community_γ20)
Metric: Adjusted Rand Index between community assignments at different γ values
R4: Lexical validation of the 2009 break (TF-IDF)
Compare mean TF-IDF vectors before vs after 2009, 2015, and 2021 on the same horizontal scale.
Max-T permutation test (1,000 permutations) for family-wise significance.
Output: figures/fig2_lexical_tfidf.pdf (2009, main figure), figures/fig2_lexical_tfidf_2015.pdf, figures/fig2_lexical_tfidf_2021.pdf (robustness controls)
Output: tables/tab2_lexical_tfidf.csv (full term-level TF-IDF comparison for 2009)
If major breakpoints and communities persist across parameter choices, we have demonstrated structural robustness of the findings.

```bash
# Prerequisites (already run, outputs cached):
# uv run python scripts/analyze_embeddings.py   -> embeddings.npy, semantic_clusters.csv
# uv run python scripts/analyze_cocitation.py    -> communities.csv

# New figures:
uv run python scripts/analyze_alluvial.py                    # main analysis
uv run python scripts/analyze_alluvial.py --robustness        # R1 + R2 sensitivity tables
uv run python scripts/analyze_genealogy.py --nodes 50
uv run python scripts/analyze_genealogy.py --nodes 200
uv run python scripts/analyze_genealogy.py --nodes 500
uv run python scripts/analyze_genealogy.py --robustness       # R3 Louvain sensitivity
```

*Verification*

analyze_alluvial.py breakpoint detection:
The breakpoint plot shows distinct peaks (not flat noise)
At least 2-3 clear peaks above the mean
Compare detected breaks to COP years: do they align? Partially? Not at all? (All answers are interesting)
analyze_alluvial.py alluvial diagram:
Uses data-derived periods (not hardcoded COP dates)
Community widths are proportional
At least one split or merge is visible between periods
analyze_genealogy.py --nodes 200 shows:
6 distinct lineage bands with different colors
Clear temporal spread (left = old papers, right = recent)
COP milestones align with visible changes in branch density
Cross-lineage arcs connect adversarial communities (e.g., OECD measurement ↔ accountability critics)
All three --nodes variants render without overlap errors
Tables are saved with correct row counts
Figures follow the same visual style as the existing Fig 1

### Risks

Risk	Mitigation
Breakpoint detection finds no clear peaks	Report as finding: the field evolved gradually, not in discrete shifts. Use equal-width periods as fallback.
Detected breaks don't match COP dates at all	Report as finding: institutional events and intellectual restructuring are decoupled. This is itself interesting.
JS divergence is flat (no clear structural drift)	Report as finding: field evolved gradually. Use equal-width periods as fallback.
JS divergence correlates with publication volume growth (|r| > 0.5)	Report correlation for both metrics. If JS is confounded but cosine distance is not, breakpoints supported only by cosine are still valid. Both metrics reported throughout -- no post-hoc switching.
Genealogy figure too cluttered at 500 nodes	That's why we generate 3 versions to eyeball
adjustText not installed	Check availability; fall back to manual offset for top-40 labels
Pre-2009 period has too few papers for meaningful clustering	Treat as single undifferentiated "roots" band in alluvial; in genealogy, place manually
User approved the plan


## Claude remarks

Plan solide, bien pensé méthodologiquement. Quelques observations critiques :

**Points forts**

- La logique centrale est cohérente : tester une périodisation exogène (COP) par détection endogène de ruptures. C'est une vraie contribution méthodologique pour l'HET computationnel.
- La double métrique (JS divergence + cosine distance) avec vérification de robustesse est correcte — tu évites le cherry-picking post-hoc.
- Le soin apporté au confound "volume de publications" est rare et bienvenu.
- Le flag ARI pour l'alignement KMeans/Louvain est intellectuellement honnête.

**Points de vigilance**

*Sur analyze_alluvial.py :*
- KMeans global k=6 est arbitraire et sensible à l'initialisation. Tu fais R2 (k=4–7) pour la robustesse, bien — mais il faudra l'écrire ainsi dans le papier dès le départ, pas en appendice.
- Le seuil z > 1.5 pour les breakpoints est raisonnable mais sa justification mérite une phrase dans le methods (pas de fondement théorique fort, c'est une convention).
- ">=2 of 3 window sizes within ±1 year" : attention aux collisions artificielles si les séries sont auto-corrélées. Pas bloquant, mais à mentionner.

*Sur analyze_genealogy.py :*
- La "citation genealogy" n'est pas une phylogénie, tu le dis — mais le terme "généalogie" peut induire en erreur des reviewers en STS. Envisage "citation DAG stratifié par communauté" dans les methods.
- Le seuil cosine < 0.4 → "peripheral" est ad hoc. Bon instinct, mais le justifier empiriquement (distribution des similarités) serait plus défendable.
- adjustText : souvent capricieux sur figures denses. Plan B (offsets manuels) risque de prendre du temps.

**Question stratégique**

Le claim de nouveauté ("to our knowledge, this specific combination has never been used to periodize an intellectual field") est fort. Avant soumission, vérifie *explicitement* Gingras & Mosbah-Natanson (Scientometrics), et les travaux de Chavalarias & Cointet (topic dynamics in science) — ils approchent parfois ce territoire.

**Verdict**

Fais-le. Le ratio effort/apport est bon, les risques sont bien balisés, et les fallbacks ("évolution graduelle" = résultat aussi) sont intellectuellement honnêtes. Le seul vrai risque est le temps sur la genealogy figure si adjustText coince.

Tu veux que je commence par quel script ?

## ChatGPT remarks

Oui — **cette version est aboutie**. Vous avez maintenant un plan qui tient à la fois :

* **épistémologiquement** (pas de phylogénie implicite, complémentarité sémantique vs citations assumée),
* **statistiquement** (métriques définies ex ante, garde-fous sur la rareté, robustesse paramétrique),
* **éditorialement** (chaîne logique Fig1→Fig2→Fig3 très lisible).

Il reste seulement quelques micro-ajustements “anti-reviewer #2” pour verrouiller.

## 1) Micro-ajustements recommandés

### A. Harmoniser un point de calendrier

Vous segmentiez parfois “pré-2005 formative phase”, parfois “1990–2005”. Décidez une convention unique dans tout le texte et les scripts :

* **Option simple** : “formative phase = 1990–2004”, breakpoints testés à partir de 2005.

### B. Clarifier `n_min = 30` et sa sensibilité

Vous fixez `n_min=30` (bien). Ajoutez une ligne :

> “We checked that results are qualitatively unchanged for n_min ∈ {20, 40}.”
> Pas besoin d’un tableau supplémentaire : une phrase suffit.

### C. “Robust breakpoint” : évitez le wording “top 3” sans contrainte de séparation

Pour éviter que deux breakpoints soient à 1–2 ans d’écart (artefact), ajoutez une contrainte :

* imposer un **espacement minimal** entre breakpoints sélectionnés (ex. ≥ 3 ans), en choisissant ensuite le breakpoint suivant le plus élevé.

### D. “k sensitivity” : ne gardez pas que JS

Vous annoncez `tab2_k_sensitivity.csv` en JS uniquement. Comme votre plan est “deux métriques partout”, faites la même chose pour le cosine drift :

* `cosine_dist_k4..k7` (ou un second fichier).
  Sinon un reviewer dira : “robustness checked only on one metric”.

### E. Louvain γ : dire explicitement sur quel graphe

Vous dites “re-run community detection” mais pas sur quoi (co-citation graph? bibliographic coupling?).

Ajoutez une phrase explicite :

* “We re-run Louvain/Leiden on the same co-citation network used to produce communities.csv (edge definition unchanged).”

Ça évite l’ambiguïté.

## 2) Sur la revendication de nouveauté méthodologique

Votre formulation “To our knowledge…” est **parfaite** (prudente et assertive).
Le seul point à corriger : “Embedding drift detection exists… but has never been applied…” → gardez le même niveau de prudence :

* “has not, to our knowledge, been used to periodize an intellectual field…”

Ça aligne le ton.

## 3) Cohérence narrative des résultats, quelle que soit l’issue

Votre section “Risks” est bonne. Un petit upgrade : annoncez explicitement que **les trois scénarios** sont interprétables :

* breaks alignent COP → “institutional milestones coincide with reorganization”
* breaks décalent COP → “decoupling”
* pas de breaks → “gradual evolution / layering rather than rupture”

Ça protège le papier contre un résultat “plat”.

## 4) Verdict final

✅ Plan **prêt à exécution** et prêt à être défendu en “methods + robustness appendix”.
Les seules choses à ajuster sont de la **rigueur de présentation** (espacement breakpoints, sensibilité n_min, k-robustness aussi sur cosine, clarification du graphe Louvain).

Si vous le souhaitez, je peux maintenant vous livrer directement (en anglais, style Oeconomia) :

1. un bloc “**Methods (Figures 2–3)**” (8–12 paragraphes),
2. une proposition de **captions** pour Fig 2a/2b et Fig 3 (avec la formulation “not a phylogeny”),
3. une mini-section “**Robustness & limitations**” qui recycle vos tables R1–R3 sans alourdir.

## ChatGPT language elements

### Method

The previous section showed that climate finance expanded rapidly as a field of publication. The question that follows is not merely one of growth, but of transformation: did the literature reorganize itself in ways that correspond to the institutional milestones commonly used to periodize climate finance, or did its intellectual structure evolve along partially independent trajectories? To address this question, we move from descriptive volume indicators to structural analysis. Figures 2 and 3 examine how the field’s internal configuration changes over time—first by detecting endogenous structural breaks in semantic community distributions, and second by visualizing the time-ordered citation genealogy of its intellectual traditions. Taken together, these figures allow us to assess whether climate finance became an “economic object” through discrete reorganizations of scholarly attention, gradual layering of problematics, or a decoupling between institutional events and intellectual restructuring.

1. Methods – Figure 2: Endogenous structural break detection

*Structural change in the intellectual field*

To assess whether the periodization of climate finance corresponds to endogenous transformations in the literature rather than to exogenous institutional milestones, we implement a data-driven structural break detection procedure on the full corpus of 9,653 publications (1990–2025).

Each paper is represented by a sentence-level embedding derived from its abstract. We first perform a global clustering of the entire embedding matrix using KMeans (k = 6). Clustering is conducted once on the full corpus to ensure a stable community ontology across time and to avoid window-specific re-fitting noise. Each publication is thus assigned a fixed semantic community label.

To assess the relation between embedding-based communities and citation-based communities, we compute the Adjusted Rand Index (ARI) on the intersection of papers present in both the embedded corpus and the co-citation community dataset. The size of this intersection (n) is reported explicitly. ARI values are interpreted descriptively (weak, moderate, strong alignment), as the two approaches capture partially distinct dimensions of intellectual structure (semantic content vs. citation behavior).

*Sliding-window structural divergence*

We detect structural shifts using a sliding-window comparison beginning in 2005. Earlier years are treated as a formative phase due to limited publication counts, which do not permit reliable window-based inference.

For each year Y ∈ [2005,2023], we define:

- a “before” window: papers published in  [Y−w,Y],
- an “after” window: papers in [Y+1,Y+1+w],

with window sizes w ∈ {2,3,4}.

Two complementary divergence metrics are computed:

- Jensen–Shannon (JS) divergence between the normalized cluster membership distributions of the two windows. This captures redistribution across intellectual communities independently of publication volume.

- Cosine distance between the mean embedding centroids of the two windows. This captures semantic drift independently of clustering.

To avoid instability due to sparse data, divergence is computed only if both windows contain at least nmin⁡=30 papers. Years failing this criterion are excluded.

To assess whether divergence merely reflects scale effects, we compute Pearson correlations between each divergence time series and yearly publication growth rates. Correlation coefficients and p-values are reported.

*Breakpoint identification*

For each metric and window size, divergence series are z-score normalized. Candidate breakpoints are defined algorithmically as local maxima exceeding 1.5 standard deviations. A breakpoint is considered:

- Strongly robust if detected (within ±1 year) in at least two window sizes for both metrics.
- Moderately robust if supported by at least two window sizes on one metric.

We select the three highest-ranked robust breakpoints, subject to a minimum spacing constraint, to define period boundaries. This procedure avoids visual judgment and ensures reproducibility.

Figure 2a displays z-scored divergence series for all window sizes, with robust breakpoints indicated. COP milestones are overlaid for comparison.

*Period reconstruction and alluvial visualization*

Using the detected breakpoints, the corpus is segmented into four data-derived periods (with 1990–2004 treated as the formative phase). Community distributions are then computed per period based on the global clustering.

Figure 2b presents an alluvial diagram in which stream widths represent the number of papers per community per period. Because community labels are fixed globally, flows reflect redistribution and growth rather than reclassification artifacts.

2. Methods – Figure 3: Citation genealogy

*Conceptual framing*

Figure 3 visualizes a time-ordered citation genealogy of intellectual communities. It is not a phylogenetic inference. Rather, it represents the internal citation directed acyclic graph (DAG) of backbone papers, structured by previously identified co-citation communities.

*Backbone selection and lineage ontology*

Three backbone variants are constructed (50, 200, 500 nodes). All use the same lineage ontology derived from Louvain community detection on the co-citation network.

The 200-node version uses the full community assignment.

The 50-node version selects the most cited papers within each community.

The 500-node version extends the backbone by assigning additional papers to the nearest community centroid in embedding space. Papers with cosine similarity below 0.4 to any centroid are flagged as peripheral and rendered with reduced opacity.

This ensures consistent lineage definitions across variants.

*Layout and citation structure*

Nodes are positioned by publication year (x-axis) and community band (y-axis). Directed edges correspond to citation links among backbone papers. Community “spines” are drawn as smooth curves through temporal centroids to enhance readability.

Cross-lineage citations are visualized as dashed arcs, highlighting intellectual transfer across traditions.

COP milestones and data-derived period bands are displayed in the background for contextual comparison.

3. Captions

Figure 2a – Structural divergence and detected breakpoints

Figure 2a. Structural divergence of the climate finance literature (2005–2023). Z-scored Jensen–Shannon divergence between community distributions is shown for window sizes
w=2,3,4
w=2,3,4. Vertical bands indicate robust breakpoints detected algorithmically. Dashed lines mark major COP milestones. Breakpoints may align with, lag behind, or diverge from institutional events.

Figure 2b – Community flows across data-derived periods

Figure 2b. Alluvial representation of semantic communities across data-derived periods. Stream width is proportional to the number of publications per community per period. Period boundaries are determined endogenously from structural divergence analysis rather than imposed exogenously.

Figure 3 – Citation genealogy of intellectual communities

Figure 3. Time-ordered citation genealogy of intellectual communities in climate finance research. Nodes represent backbone publications (size proportional to citations). Colors indicate co-citation communities. Directed edges represent citation links. The figure visualizes intellectual inheritance and cross-community transfer, not inferred ancestry.

4. Robustness and limitations

*Robustness checks*

Four sensitivity analyses are conducted:

1. Window-size sensitivity: breakpoints are computed for w=2,3,4.

2. Cluster-number sensitivity: global clustering repeated for k=4,5,6,7.

3. Community-resolution sensitivity: Louvain resolution parameter varied (when supported).

4. Lexical validation and comparative control (2009 vs. 2015, 2021).

Major breakpoints and community structures persist across parameter choices, indicating structural robustness.

*R4. Lexical validation of the 2009 break*

The structural break detected at 2009 relies on sentence embeddings, which are semantically rich but opaque. To validate this finding with a transparent lexical test, we compare mean TF-IDF vectors before and after each candidate break year. For a given year Y, period A comprises all abstracts published before Y, and period B comprises abstracts published in [Y+1, Y+3]. We fit a single TF-IDF vectorizer (unigrams and bigrams, sublinear term frequency, English stop words removed) on the pooled corpus, then compute the mean TF-IDF vector per period and their difference. Statistical significance is assessed via a max-T permutation test (1,000 permutations of period labels, family-wise error rate controlled at α = 0.05).

We apply this procedure to three years: the data-derived break (2009) and the two COP-imposed supplements (2015, 2021). All three comparisons use the same shared horizontal scale to enable visual comparison of effect sizes.

*2009 (n = 41 vs. 408).* The lexical contrast is massive (ΔTFIDF up to ±0.02). Terms enriched before 2009—sustainable development, growth, risk, MERV (monitoring, evaluating, reporting, verifying), Kyoto protocol, abatement, industrialized countries—belong to a vocabulary of development aid and international negotiation. Terms enriched after 2009—climate finance, carbon, finance, fund, UNFCCC, Copenhagen, private, low carbon—signal the emergence of a distinct financial vocabulary. The two lexical worlds are nearly disjoint, confirming a paradigmatic reorientation rather than a gradual shift. The permutation threshold is wide (p < 0.05 at |ΔTFIDF| = 0.023) due to the small pre-2009 corpus, yet several pre-2009 terms still exceed it.

*2015 (n = 958 vs. 1,111).* The lexical shift is thematically targeted but 3–4× smaller in magnitude. Pre-2015 terms (developing countries, Copenhagen, CDM, carbon markets, NAMAs) give way to post-2015 terms (Paris, Paris Agreement, nationally determined contributions, SDGs, green bonds). The field's core vocabulary (climate, finance, mitigation) remains stable. Only "Paris," "Paris Agreement," and "developing countries" exceed the p < 0.01 threshold. This is an institutional reanchoring within an established field, not a structural break.

*2021 (n = 3,330 vs. 4,007).* The contrast is again modest. Pre-2021 terms (mitigation, developing countries, UNFCCC, REDD, negotiations) yield to post-2021 terms (green, green finance, transition, ESG, sustainability, COVID, pandemic, net zero). Nearly all terms are statistically significant due to the large sample, but effect sizes are small (ΔTFIDF < 0.007). This confirms a thematic inflection—from negotiation-centered to transition/ESG-centered discourse—rather than a lexical rupture.

*Interpretation.* The three-way comparison demonstrates that the 2009 break is qualitatively different from the 2015 and 2021 transitions. Only 2009 produces a wholesale lexical reorientation (two nearly disjoint vocabularies). The later transitions reorganize emphasis within a vocabulary that is already constituted. This converges with the embedding-based structural break detection, which identifies 2009 as the sole robust endogenous breakpoint (z > 3, stable across window sizes and cluster counts), and provides independent lexical evidence that climate finance crystallized as a distinct discursive object around 2009.

*Limitations*

Several limitations should be noted.

First, embedding-based communities reflect semantic proximity rather than citation behavior. Divergences between embedding and co-citation structures are therefore interpreted as complementary perspectives rather than inconsistencies.

Second, structural divergence metrics may partially correlate with publication growth. Correlation statistics are reported to assess this possibility.

Third, early years of the corpus contain limited observations; they are therefore treated as a formative phase rather than subjected to break detection.

Finally, the genealogy figure represents citation structure among backbone papers and does not imply causal or evolutionary descent.
