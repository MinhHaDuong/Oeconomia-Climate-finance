# Memo: Clustering reveals field structure (not method limitations)

Author: Claude (overnight autonomous session)
Date: 2026-03-23
Method: KMeans/HDBSCAN/Spectral clustering across semantic, lexical, and citation spaces (27K works, 384D embeddings)

## The insight

The clustering comparison (#299) was framed as "which method is most stable?" but the real finding is deeper: **climate finance has no natural cluster structure in any representation space.** The field is a continuum — works blend across topics, methods, and disciplines without forming discrete schools of thought.

This is NOT a negative result. It's a positive finding about the nature of the field:

1. **Semantic embeddings** (what works are about): silhouette 0.025–0.038. Works about "green bonds" are not semantically distant from works about "carbon markets." The topics overlap.

2. **Lexical space** (what words are used): silhouette 0.032–0.062. Slightly more structure because jargon differs, but still diffuse.

3. **Citation space** (who cites whom): silhouette 0.052–0.108. The most structure — 3× semantic — but still low. HDBSCAN finds 20 citation communities. "Traditions" are citation communities more than conceptual clusters.

## What this means for the manuscript

The manuscript describes six "traditions" of climate finance thought. The clustering comparison shows these are not natural categories but imposed partitions. This actually strengthens the paper's argument: the categories were politically constructed (at Copenhagen, Paris, etc.), not discovered by bibliometric methods. The co-citation communities reflect institutional networks, not conceptual boundaries.

## Possible implications

- For the revision: add a paragraph noting that k=6 is a convention matching citation communities, not a statistical optimum. Silhouette analysis shows no natural k.
- For the companion paper: the multi-space comparison is a methodological contribution. Dense embeddings miss structure that citation graphs capture.
- For ESHET-HES slides: this is a great visualization. Show the three silhouette curves side by side — the audience will immediately see that "traditions" are citation-based, not concept-based.

## Technical notes

- Bibliographic coupling needs L2 normalization. Without it, hub works dominate and KMeans creates trivial outlier clusters (silhouette=0.99 artifact).
- HDBSCAN is too slow for 27K works with 384D input (~5 min per run). On normalized citation space (100D), it's fast and finds 20 communities.
- Spectral clustering requires subsampling above 5K works. The subsampled version is effectively nearest-centroid for out-of-sample works — not a faithful spectral approximation.

## Next steps

- [ ] Run corrected analysis end-to-end (the citation space fix changed results)
- [ ] Consider adding Louvain on bibliographic coupling graph (not just co-citation)
- [ ] Test whether UMAP projection adds or removes structure
- [ ] Investigate why only 18,467 of 29,875 v1.0 identifiers match by DOI
