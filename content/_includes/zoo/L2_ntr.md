## L2. Novelty, Transience, Resonance {#sec-l2}

### Principle

Barron et al. (2018) decompose textual change into three orthogonal quantities:
*novelty* (how different a work is from past discourse),
*transience* (how different a work's discourse is from the future),
and *resonance* (novelty that persists into the future; novelty minus transience).
Applied to yearly aggregates rather than individual works,
these measure whether a given year's vocabulary introduced genuinely new concepts
or was simply an ephemeral departure.

### Definition

For year $t$ with forward/backward window $w$:

$$\text{Novelty}(t) = D_{KL}(P_t \| P_{t-w:t-1})$$
$$\text{Transience}(t) = D_{KL}(P_t \| P_{t+1:t+w})$$
$$\text{Resonance}(t) = \text{Novelty}(t) - \text{Transience}(t)$$

where $P_\tau$ is the aggregated TF-IDF distribution for the year or window $\tau$.

*Script:* `scripts/_divergence_lexical.py`, method `L2` (channels: novelty, transience, resonance).

### Principle figure

![](figures/schematic_L2_ntr.png){width=100%}

*NTR: novelty (backward KL) and transience (forward KL) arrows around focal year t=2005.*

### Advantages, biases, limitations

**Advantages.** Asymmetric decomposition is more informative than a symmetric distance. Resonance identifies *lasting* innovations. Three derived signals from one computation.

**Biases.** KL divergence is unbounded and undefined when $P_t$ has support outside $P_{t-w:t-1}$ (rare terms in small windows); we add Laplace smoothing ($\epsilon = 10^{-10}$). Results for early years (1990–1998) are unstable due to sparse corpora.

**Limitations.** Year-level aggregation discards within-year heterogeneity. Sensitivity to smoothing parameter.

### Null expectation

Under $H_0$ (both windows drawn from the same distribution), NTR should be near zero.
In the cold-start zone (1990–1998), before-windows contain as few as 10–20 papers,
severely under-representing the vocabulary.
At small $n_\text{before}$, many terms are absent from the before-window by sampling chance alone —
inflating the novelty component regardless of any true distributional shift.
This is a small-sample artefact, not a structural break:
NTR estimates for $t < 1999$ should be interpreted cautiously.

### Corpus results

![](figures/fig_zoo_L2.png){width=100%}

*Cross-year Z-score for L2 (NTR), w=2–5.*

Key values (w=3): peak $Z = +3.0$ at 1999, monotonic decline. Same convergence pattern as S methods and L1.
The 1999 peak falls immediately after the 1990–1998 cold-start zone flagged above as unstable, so the precise year should be read as suggestive rather than definitive; the monotonic decline from the late 1990s onward is the robust signal.

### References

Seminal: @barron2018individuals (Barron et al. 2018, "Individuals, Institutions, and Innovation in the Debates of the French Revolution", *PNAS*).
Recent analogue: @murdock2017exploration (Murdock et al. 2017, "Exploration and Exploitation of Victorian Science").
