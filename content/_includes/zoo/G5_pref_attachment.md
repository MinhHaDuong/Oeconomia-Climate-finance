## G5. Preferential Attachment Exponent Divergence {#sec-g5}

### Principle

Preferential attachment (Barabási-Albert) is the "rich get richer" mechanism: a new paper is more likely to cite already highly-cited papers. This generates a power-law in-degree distribution $P(k) \propto k^{-\gamma}$. A structural break changes the citation dynamics — for instance, a new funding institution may redirect citations to a new set of authoritative texts — and should shift the power-law exponent $\gamma$. G5 measures the difference between the fitted $\gamma$ before and after the candidate break year.

### Definition

For each window, fit $\gamma$ by maximum likelihood estimator for a discrete power law [@clauset2009power]:

$$\hat{\gamma} = 1 + n\left[\sum_{i=1}^n \ln \frac{k_i}{k_{\min} - \frac{1}{2}}\right]^{-1}$$

where $k_{\min} = 1$ and the sum runs over all in-degrees $k_i \geq k_{\min}$ in the window subgraph.

$$D_{\text{G5}}(t, w) = |\hat{\gamma}_{\text{after}} - \hat{\gamma}_{\text{before}}|$$

*Script:* `scripts/_citation_methods.py`, `G5_pref_attachment`.

### Principle figure

![](figures/schematic_G5_pref_attachment.png){width=100%}

*Preferential attachment: log-log in-degree scatter with two power-law fits (γ_before, γ_after).*

### Advantages, biases, limitations

**Advantages.** Theoretically motivated: PA is the dominant citation mechanism [@barabasi1999emergence]. Power-law exponent is a single, interpretable parameter. Robust to network size differences (exponent is scale-free).

**Biases.** Power-law fit assumes a true power law; real citation distributions are better described as log-normal or stretched exponential for in-degrees $k < 50$. Estimator uses $k_{\min} = 1$ for simplicity; goodness-of-fit test (Clauset KS test) is not applied per window.

**Limitations.** Absolute difference $|\hat\gamma_{\text{after}} - \hat\gamma_{\text{before}}|$ does not have a natural sign; a shift toward a flatter or steeper distribution are both reported as positive. Does not distinguish cause (new funding, new institutions, bandwagon effects).

### Corpus results

![](figures/fig_zoo_G5_pref_attachment.png){width=100%}

*Cross-year Z-score for G5 (PA exponent), w=2–5. **Peak at 2007** confirms structural break in citation topology.*

**Key result:** Cross-year $Z$-scores (w=3) peak at **2007** ($Z = +2.96$), then decline through 2013–2015.
G5 detects the post-Stern/UNFCCC-Bali structural break unambiguously, with the 2007 Z-score exceeding $+2$.
The power-law exponent of the in-degree distribution shifts significantly in the window centred on 2007,
indicating that the citation dynamics of the field changed — new authoritative texts captured a larger share of citations, consistent with the emergence of IPCC reports and policy framework documents as citation hubs.

### References

Seminal: @barabasi1999emergence (Barabási & Albert 1999, "Emergence of scaling in random networks", *Science*).
Recent analogue: @clauset2009power (Clauset et al. 2009, "Power-law distributions in empirical data", *SIAM Review* — standard MLE and goodness-of-fit for power laws, the method we use).
