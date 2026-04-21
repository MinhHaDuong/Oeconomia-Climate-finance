## G2. Spectral Gap Divergence {#sec-g2}

### Principle

The spectral gap of a graph — the difference between the largest and second-largest eigenvalue of the adjacency or Laplacian matrix — measures how well-connected the graph is.
A structural break that reorganises citation flow patterns should manifest as a change in the spectral gap.
We compare the spectral gaps of the before- and after-window subgraphs.

### Definition

$$D_{\text{G2}}(t, w) = |\lambda_1^{after} - \lambda_2^{after}| - |\lambda_1^{before} - \lambda_2^{before}|$$

where $\lambda_1 \geq \lambda_2 \geq \cdots$ are the eigenvalues of the normalised Laplacian.
We use the top-2 eigenvalues via `scipy.sparse.linalg.eigsh`.

*Script:* `scripts/_citation_methods.py`, `G2_spectral`.

### Principle figure

![](figures/schematic_G2_spectral.png){width=100%}

*Spectral gap: 10 smallest Laplacian eigenvalues for 2000–2004 (blue) and 2007–2011 (red) citation subgraphs. The largest gap (shaded) locates the natural cluster count. After Von Luxburg (2007, Fig. 4).*

### Advantages, biases, limitations

**Advantages.** Single scalar summary of global connectivity. Related to mixing time and community separability.

**Biases.** Sparse graphs (early years) have degenerate spectra; we require $\geq 50$ nodes per window. Signed difference rather than absolute distance loses information.

**Limitations.** Shows flat/convergence signal on this corpus (peak at 1999, Z = +3.8); no 2007 peak.

### Corpus results

![](figures/fig_zoo_G2_spectral.png){width=100%}

*Cross-year Z-score for G2 (spectral gap), w=2–5.*

Key values (w=3): peak $Z = +3.8$ at 1999, flat thereafter. Convergence but not structural break.

### References

Seminal: @von2007tutorial (Von Luxburg 2007, "A Tutorial on Spectral Clustering").
Recent analogue: @newman2006modularity.
