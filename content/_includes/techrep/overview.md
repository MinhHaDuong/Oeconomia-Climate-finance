# Overview

This document surveys the structural break detection methods applied to the climate finance corpus
({{< meta corpus_total >}} works, 1990--2024).
Each method answers the same question in a different vocabulary:
*does the distribution of works written before year $t$ differ from the distribution of works written after $t$?*
We apply a sliding window of $w$ years on each side of the candidate break year.^[Throughout this report we show $w \in \{2, 3, 4\}$. The companion paper reports $w=3$ as the default lead window, with $w \in \{2, 4\}$ as robustness checks.]

Methods are grouped into three layers:

- **Part S — Semantic.** Compare full embedding distributions: each work is a point in the BAAI/bge-m3 embedding space ({{< meta emb_dimensions >}} dimensions). These methods detect distributional shift in *what the field talks about*.
- **Part L — Lexical.** Compare TF-IDF vocabulary distributions. Complementary to semantic methods; more interpretable (discriminating terms are directly readable).
- **Part G — Citation graph.** Compare citation network topology: degree distributions, community structure, centrality. These methods detect changes in *how knowledge flows* rather than *what is said*.
- **C2ST (Classifier two-sample tests).** C2ST\_embedding lives in Part S; C2ST\_lexical lives in Part L. Each asks the same meta-check question — can a classifier distinguish "before" from "after" better than chance? — in its respective feature space.
