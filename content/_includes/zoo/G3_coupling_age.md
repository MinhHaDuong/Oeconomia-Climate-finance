## G3. Bibliographic Coupling Age Shift {#sec-g3}

### Principle

Bibliographic coupling links two papers that cite a common third paper.
The *age* of bibliographic coupling measures how far back in time a paper's references reach.
A structural shift is visible as a change in the mean age of references cited by papers in successive cumulative windows — a field that matures stops citing the same canonical texts and begins referencing a new generation of foundational papers.

### Definition

Uses a **cumulative window**: all papers published up to year $t-1$ (before group) vs. all papers published up to year $t$ (after group).

$$D_{\text{G3}}(t) = \bar{a}_{t} - \bar{a}_{t-1}$$

where $\bar{a}_t$ is the mean age of cited works (= year of citing paper $-$ year of cited paper)
for all citations made by papers published in year $t$.

*Script:* `scripts/_citation_methods.py`, `G3_coupling_age` (window = "cumulative").

### Principle figure

![](figures/schematic_G3_coupling_age.png){width=100%}

*Citation age histograms (log scale) with exponential decay fit for 2000–2004 and 2007–2011 citing windows. The shift in mean age (Δ=1.4 yr) is annotated. After Price (1965).*

### Advantages, biases, limitations

**Advantages.** Interpretable without graph theory. Detects "canon formation" (convergence on a short list of seminal papers).

**Biases.** Cumulative windows mean each year adds data to both groups; the before/after comparison is not symmetric. Dominated by highly prolific citing years.

**Limitations.** Cumulative design makes it unsuitable for detecting point-in-time structural breaks; better as a slow-moving indicator of field maturation.

### Corpus results

![](figures/fig_zoo_G3_coupling_age.png){width=100%}

*Cross-year Z-score for G3 (bibliographic coupling age), cumulative window.*

### References

Seminal: @kessler1963bibliographic (Kessler 1963, "Bibliographic coupling between scientific papers").
Recent analogue: @min2021measuring (Min et al. 2021, "Measuring knowledge accumulation in science").
