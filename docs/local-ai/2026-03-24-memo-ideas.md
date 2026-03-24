# Memo: Seven exploration branches from clustering analysis

Author: Claude (overnight autonomous session)
Date: 2026-03-24
Method: Recursive brainstorm from clustering comparison findings (#299)

## Branch 1: UNFCCC-guided topic taxonomy (t299-explore-unfccc)

The UNFCCC negotiations organized climate finance into specific rooms/workstreams:
CDM/JI, adaptation fund, GCF design, long-term finance, NCQG, loss and damage.
Does the corpus follow this organizational structure?

**Idea**: Build a supervised classification using UNFCCC negotiation topics as labels.
Assign papers to UNFCCC tracks based on keyword matching, then test whether
these assignments correlate with unsupervised clusters. If they do, the academic
field mirrors the diplomatic structure — evidence for co-production.

## Branch 2: Dynamic topic evolution (t299-explore-dynamic)

Static clustering misses the flow. Papers don't stay in one tradition — authors
move between topics, new topics emerge, old ones merge.

**Idea**: Implement a temporal topic flow analysis. For each year-pair, compute
the transition matrix: how many papers in cluster C at time t are in cluster C'
at time t+1 (using bibliographic coupling to track lineage). This gives a Markov
chain of topic evolution. Where does it show splitting? Merging? Birth? Death?

## Branch 3: Period detection via change-point analysis (t299-explore-changepoint)

The temporal silhouette analysis shows one structural transition ~2007, but our
method (rolling window silhouette) is ad hoc. Apply proper change-point detection:

**Idea**: Use Bayesian change-point detection on the annual silhouette time series
in each space. Test whether the data support 1, 2, or 3 change-points. If 1,
the three-act structure is not supported by the data.

## Branch 4: Citation community persistence (t299-explore-persistence)

HDBSCAN finds 20 citation communities. Do the same communities persist across
time windows, or do they form, merge, and dissolve?

**Idea**: Run HDBSCAN on citation space per-period, then track communities via
maximum ARI alignment between adjacent windows. Build a "community genealogy"
showing which early communities persist and which are absorbed.

## Branch 5: Multilingual structure revisited (t299-explore-multilingual)

Language doesn't create clustering in the semantic space, but does it create
structure in the citation space? Non-English works might cite different literatures.

**Idea**: Compare citation coupling vectors for EN vs non-EN works. Do French
climate finance papers cite different references than English ones? This tests
whether linguistic communities create citation silos even when topics overlap.

## Branch 6: The $100bn accounting debate as a case study (t299-explore-100bn)

The $100bn pledge (Copenhagen 2009) generated a specific sub-literature on
accounting, measurement, and transparency. This is a well-defined sub-topic
that should be identifiable in all three spaces.

**Idea**: Identify the $100bn accounting papers (keyword: "100 billion" OR
"climate finance accounting" OR "new and additional"). Test whether this
sub-corpus forms a cluster in semantic, lexical, and citation spaces. If it
clusters in citation but not semantic space, that confirms the social-structure
hypothesis.

## Branch 7: Comparing our silhouette results with the bibliometric literature (t299-explore-benchmarks)

Are near-zero silhouette scores typical in bibliometric studies? Or is climate
finance unusually diffuse? Comparing with published silhouette values from
other field-mapping studies would contextualize our finding.

**Idea**: Survey published bibliometric studies that report silhouette scores.
Collect: field, corpus size, embedding method, silhouette range. This turns
our "limitation" into a comparative finding.
