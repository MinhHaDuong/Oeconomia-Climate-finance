## G4. Cross-Tradition Citation Ratio {#sec-g4}

### Principle

The corpus is divided into three intellectual traditions by a K-means cluster label
(finance, development economics, and physical science). The cross-tradition ratio measures
what fraction of citations cross tradition boundaries — a rising ratio signals
field integration, a falling ratio signals specialisation.

### Definition

Cumulative window. Let $C_{within}(t)$ and $C_{cross}(t)$ be the counts of within- and cross-tradition citations by papers published up to year $t$.

$$D_{\text{G4}}(t) = \frac{C_{cross}(t)}{C_{within}(t) + C_{cross}(t)}$$

*Script:* `scripts/_citation_methods.py`, `G4_cross_tradition`.

### Principle figure

![](figures/schematic_G4_cross_tradition.png){width=100%}

*Cross-tradition citation flows between finance, development economics, and physical science clusters. Arrow width ∝ citation volume; self-loops = within-tradition. G4=72.5% cross-tradition. After Börner (2010), Klavans & Boyack (2017).*

### Advantages, biases, limitations

**Advantages.** Direct measure of cross-pollination between sub-fields.

**Biases.** Tradition labels come from K-means clustering with a fixed $K$; sensitive to $K$ and to which papers are assigned to which cluster. Cumulative design, same caveat as G3.

**Limitations.** Not a structural break detector; best used as a slow-moving description of integration dynamics.

### Corpus results

![](figures/fig_zoo_G4_cross_tradition.png){width=100%}

*Cross-year Z-score for G4 (cross-tradition ratio), cumulative window.*

### References

Seminal: @price1965networks (Price 1965, "Networks of Scientific Papers").
Recent analogue: @battiston2019taking.
