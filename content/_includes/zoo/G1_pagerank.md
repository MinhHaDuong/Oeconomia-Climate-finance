## G1. PageRank Distribution Divergence {#sec-g1}

### Principle

PageRank assigns each paper an importance score based on the centrality of its citers.
A structural shift in the field should be visible as a change in the PageRank distribution:
key nodes (highly cited, highly authoritative papers) should shift from pre-2007 authorities to post-2007 ones.
We compute PageRank on the subgraph within each window and measure JS divergence between the two distributions.

### Definition

PageRank scores $\pi_i$ satisfy $\pi = \alpha M^T \pi + (1-\alpha) \mathbf{1}/n$
with damping factor $\alpha = 0.85$ and column-stochastic adjacency $M$.
Window JS divergence:

$$D_{\text{G1}}(t, w) = \text{JS}\!\left(\text{hist}(\pi_{\text{before}}),\; \text{hist}(\pi_{\text{after}})\right)$$

where histograms use 50 log-spaced bins over $[10^{-5}, 1]$.

*Script:* `scripts/_citation_methods.py`, `G1_pagerank`.

### Principle figure

![](figures/schematic_G1_pagerank.png){width=100%}

*PageRank divergence: overlapping log-scale histograms before/after with 5-node hub inset.*

### Advantages, biases, limitations

**Advantages.** Sensitive to changes in the authority structure of the field, not just citation counts. Well-understood algorithm.

**Biases.** PageRank is sensitive to the size and density of the subgraph; growing corpus means growing graphs. Equal-window balancing (`equal_n: true`) partially mitigates this. Histogram binning choice affects measured JS divergence.

**Limitations.** Shows convergence signal on this corpus (peak at 1999, monotonic decline); not sensitive to 2007/2013 topology change in our corpus.

### Corpus results

![](figures/fig_zoo_G1_pagerank.png){width=100%}

*Cross-year Z-score for G1 (PageRank JS), w=2–5.*

Key values (w=3): peak $Z = +1.3$ at 1999. Weak convergence signal.

### References

Seminal: @page1998pagerank (Page et al. 1998, *The PageRank Citation Ranking: Bringing Order to the Web*).
Recent analogue: @walker2007ranking (Walker et al. 2007, "Ranking Scientific Publications Using a Simple Model of Network Traffic").
