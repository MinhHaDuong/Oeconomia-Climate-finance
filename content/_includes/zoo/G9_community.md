## G9. Louvain Community Divergence {#sec-g9}

### Principle

Community detection partitions the citation network into groups of papers that cite each other more than they cite outside the group.
The Louvain algorithm maximises modularity to find these groups efficiently.
A structural break should reorganise community membership: the communities that dominated before 2007
should lose share, and new communities should emerge after 2007.
We compare the community-share vectors of the before- and after-window subgraphs using JS divergence.
This is the closest graph-theoretic analogue to the K-means cluster JS divergence used in the original
`compute_breakpoints.py` pipeline.

### Definition

Run Louvain on the union subgraph of both windows; obtain community labels $c_i$ for each node.
Let $q_k^{before}$ = fraction of before-window papers assigned to community $k$,
$q_k^{after}$ = fraction of after-window papers assigned to community $k$.

$$D_{\text{G9}}(t, w) = \text{JS}(q^{before}, q^{after})$$

*Script:* `scripts/_divergence_community.py`, `G9_community`.

### Principle figure

![](figures/schematic_G9_community.png){width=100%}

*Community divergence: before/after force-directed layouts with community-share stacked bars.*

### Advantages, biases, limitations

**Advantages.** Most interpretable graph method: communities can be labelled by their dominant topics. Direct successor to the K-means JS divergence of the original pipeline.

**Biases.** Louvain is non-deterministic (random seed-dependent); community labels are unstable across runs (label-switching). The number of communities $K$ is determined automatically by modularity maximisation, which can overfit for dense subgraphs. Community identity across time is not guaranteed — community 1 before 2007 may not correspond to community 1 after 2007.

**Limitations.** Despite its conceptual appeal, G9 shows the same convergence signal as S and L methods (peak at 2001, monotonic decline) rather than a 2007 structural break. This suggests that Louvain community membership — like raw distribution divergence — measures *field heterogeneity* rather than *citation topology change*. G5 and G6, which track the degree distribution directly, are more sensitive to the institutional shift at 2007.

### Corpus results

![](figures/fig_zoo_G9_community.png){width=100%}

*Cross-year Z-score for G9 (community JS), w=2–5. Peak at 2001 — field convergence, not 2007 break.*

Key values (w=3): peak $Z = +2.3$ at 2001, monotonic decline to $Z \approx -1.4$ at 2010.
No peak at 2007 or 2013.

**Interpretation.** Community divergence is highest in the 1990s/early 2000s, when climate finance was a loose assembly of distinct intellectual communities.
As the field institutionalised, papers increasingly cited across communities,
and the community-share vectors of before/after windows converged.
The same story told by S1–S4 and L1, from a graph perspective.

### References

Seminal: @blondel2008fast (Blondel et al. 2008, "Fast unfolding of communities in large networks", *Journal of Statistical Mechanics*).
Recent analogue: @rosvall2019different (Rosvall et al. 2019, "Different approaches to community detection").
