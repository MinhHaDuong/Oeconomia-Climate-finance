## G7. Disruption Index CD {#sec-g7}

### Principle

The disruption index CD [@funk2017dynamic] distinguishes *consolidating* papers (that are cited along with their references — building on prior work) from *disrupting* papers (that are cited *instead of* their references — replacing prior work). Disrupting papers redirect the field; consolidating papers deepen it. A structural break at 2007 or 2013 should appear as a spike in the proportion of disrupting papers.

### Definition

Cumulative window. For paper $i$ let $f_i$ = papers that cite $i$ but not $i$'s references,
$b_i$ = papers that cite $i$ and also at least one of $i$'s references,
$c_i$ = papers that cite only $i$'s references (not $i$ itself).

$$CD_i = \frac{f_i - b_i}{f_i + b_i + c_i}$$

$CD \in [-1, 1]$; $CD > 0$ = disrupting, $CD < 0$ = consolidating.
Corpus signal: mean $CD$ of papers published in year $t$.

*Script:* `scripts/_citation_methods.py`, `G7_disruption`.

### Principle figure

![](figures/schematic_G7_disruption.png){width=100%}

*Disruption taxonomy: focal paper (gold) + references (grey, inner ring) + citing papers coloured by type. Red f = cite focal only; orange b = cite both; blue c = cite references only. CD = (f−b)/(f+b+c). After Funk & Owen-Smith (2017, Fig. 1).*

### Advantages, biases, limitations

**Advantages.** Theoretically motivated distinction between consolidation and disruption. Widely used in science-of-science literature [@park2023papers].

**Biases.** Requires forward citations that accumulate over many years; recent papers (after 2018) have insufficient citation time. Cumulative design. Sensitive to database completeness (missing references inflate $f_i$).

**Limitations.** Not a structural break detector in the distributional sense; reports average annual $CD$ trend rather than a window-based divergence. Recent work questions whether the global decline in $CD$ reflects true science dynamics or database artefacts.

### Corpus results

![](figures/fig_zoo_G7_disruption.png){width=100%}

*Cross-year Z-score for G7 (disruption index CD), cumulative window.*

### References

Seminal: @funk2017dynamic (Funk & Owen-Smith 2017, "A Dynamic Network Measure of Technological Change", *Management Science*).
Recent analogue: @park2023papers (Park et al. 2023, "Papers and patents are becoming less disruptive over time", *Nature*).
