## G8. Mean Betweenness Centrality {#sec-g8}

### Principle

Betweenness centrality of a node measures how often it lies on the shortest paths between other nodes.
A high-betweenness node is a broker: it connects otherwise distant parts of the citation network.
A structural shift may produce or destroy brokers — e.g., a new IPCC report bridging finance and physical science.
We compare the mean betweenness centrality of the before- and after-window subgraphs.

### Definition

$$B_i = \sum_{s \neq i \neq t} \frac{\sigma_{st}(i)}{\sigma_{st}}$$

where $\sigma_{st}$ is the count of shortest paths from $s$ to $t$,
and $\sigma_{st}(i)$ is the count passing through $i$.
Normalised to $[0,1]$ by dividing by $(n-1)(n-2)$.

$$D_{\text{G8}}(t, w) = |\bar{B}_{\text{after}} - \bar{B}_{\text{before}}|$$

*Script:* `scripts/_citation_methods.py`, `G8_betweenness` (sampled approximation for $n > 500$).

### Principle figure

![](figures/schematic_G8_betweenness.png){width=100%}

*Star, ring, and chain topologies with node size ∝ betweenness centrality. Star maximises the hub's betweenness; ring distributes it equally; chain concentrates it at the middle. After Freeman (1977, Fig. 2).*

### Advantages, biases, limitations

**Advantages.** Captures brokerage role; theoretically linked to information flow.

**Biases.** Betweenness computation is $O(nm)$ exact, $O(km)$ for $k$-sampled approximation; sampling introduces variance. Mean betweenness is dominated by a few high-centrality nodes; median would be more robust.

**Limitations.** Shows weak signal on this corpus; dominated by the large variance from sampling approximation.

### Corpus results

![](figures/fig_zoo_G8_betweenness.png){width=100%}

*Cross-year Z-score for G8 (betweenness), w=2–5.*

### References

Seminal: @freeman1977set (Freeman 1977, "A Set of Measures of Centrality Based on Betweenness").
Recent analogue: @leydesdorff2007betweenness (Leydesdorff 2007, "Betweenness Centrality as an Indicator of the Interdisciplinarity of Scientific Journals", *JASIST*).
