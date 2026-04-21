## L3. Term Burst Detection {#sec-l3}

### Principle

Burst detection identifies terms whose frequency jumps sharply in a short window,
signalling the emergence of a new concept or the adoption of new language.
Unlike the distribution-level methods L1 and L2, L3 operates at the term level:
it returns a ranked list of bursting terms for each year,
providing a lexical fingerprint of each transition.

### Definition

We implement a simplified Kleinberg automaton for each term $v$:
term frequency $f_v(t)$ is modelled as a Poisson process with rate $\lambda_v(t)$.
A burst at year $t$ is flagged when the frequency exceeds a threshold
$\lambda_v^\star = \bar{f}_v + z_\text{thresh} \cdot \hat{\sigma}_{f_v}$,
where $\bar{f}_v$ and $\hat{\sigma}_{f_v}$ are the mean and standard deviation of term $v$'s frequency
across all years, and $z_\text{thresh} = 2$.
The burst $Z$-score is $(f_v(t) - \bar{f}_v) / \hat{\sigma}_{f_v}$.

*Script:* `scripts/_divergence_lexical.py`, method `L3` (output: term × year matrix of burst $Z$-scores).

### Principle figure

![](figures/schematic_L3_burst.png){width=100%}

*Burst detection: annual frequency for 'green finance', 'climate risk', 'green bond' with burst threshold.*

### Advantages, biases, limitations

**Advantages.** Term-level interpretability. Requires no embedding; applicable to any text corpus. Can identify the specific vocabulary associated with each structural break.

**Biases.** Threshold $z_\text{thresh}$ is a free parameter. Rare terms (frequency < 5/year) are excluded to avoid false positives from sparse counts.

**Limitations.** Does not aggregate into a single divergence signal; the output is a list of bursting terms, not a scalar. Integration into the zoo figure requires a derived aggregate (e.g., count of bursting terms per year).

### Corpus results

![](figures/fig_zoo_L3.png){width=100%}

*Cross-year Z-score for L3 (burst term count), w=2–5.*

### References

Seminal: @kleinberg2003bursty (Kleinberg 2003, "Bursty and Hierarchical Structure in Streams", *Data Mining and Knowledge Discovery*).
Recent analogue: @tattershall2020detecting (Tattershall, Nenadic & Stevens 2020, "Detecting bursty terms in computer science research", *Scientometrics*).
