# Companion Paper Assessment (2026-04-14)

## Status: not publishable as-is

Three structural problems prevent submission as a methods paper.

### 1. Duplication with technical report

Sections 4.1–4.5 use the same `{{< include >}}` files as the technical
report's Part II: embedding-generation, structural-breaks, alluvial-diagram,
bimodality-analysis, pca-scatter, core-vs-full. The companion paper wraps
these in a literature review and discussion; the technical report presents
them as pipeline documentation. Same content, different framing.

### 2. Two orthogonal contributions in one paper

The title promises "Structural Breaks *and* Polarization." These are
independent methods solving different problems:

- **Break detection**: sliding-window divergence, censored gap, two-level
  design. This is a changepoint-methods contribution.
- **Polarization detection**: seed-axis projection, GMM bimodality, PCA
  loading analysis. This is a science-studies/polarization contribution.

A reviewer expert in one domain will not care about the other. The paper
is diffuse and lacks a single clear contribution.

### 3. Circular validation

The framework is "validated" only on climate finance — the dataset it was
developed on. Section 6.3 lists candidate applications (AI ethics,
sustainable finance, global health) but tests none. A methods paper must
demonstrate the method recovers known breaks. Three candidates:

- **COVID-19 in public health** (2020) — sharp, unambiguous
- **Deep learning in AI/ML** (2012, AlexNet) — well-documented paradigm shift
- **Financial crisis in economics** (2008) — proximate to climate finance

### 4. Break detection oversells its findings

The mid-2010s JS divergence signal is real (elevated z-scores 2013–2016
across all window sizes). The censored-gap technique suppresses this by
design. The Oeconomia paper's framing ("corroborates" a historically-
grounded periodization) is honest. The companion paper's framing
("endogenous break detection contradicts COP-milestone chronology") is not.

## Recommendation

Do not submit. The method sections already live in the technical report.
If a methods paper is worth pursuing later:

1. Pick ONE contribution (break detection only).
2. Validate on 3 external cases with known breaks.
3. Use climate finance as the motivating application, not the only test.
4. Correct section 5.1 to acknowledge the mid-2010s JS signal honestly.

The bimodality finding (efficiency-accountability) is interesting but
belongs in a different paper with a science-studies audience.

## What to keep

- The abstract and polish from ticket 0015 improve the document for
  anyone reading it as a technical companion to the Oeconomia paper.
- The literature review (Section 2) is well-researched and reusable.
- The bib entries added for the NCC draft are useful regardless.
