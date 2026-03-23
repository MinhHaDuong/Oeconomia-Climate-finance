# Data paper: gap analysis for Scientific Data submission

Date: 2026-03-20

## Status

The `data-paper.qmd` draft now follows the Scientific Data Data Descriptor
format. This document lists what remains before submission.

## Ready

- [x] Title (descriptive, includes corpus scope and methods)
- [x] Abstract (123 words, under 170 limit, no refs, no findings)
- [x] Background & Summary (395 words, under 700 limit)
- [x] Methods (via includes: corpus-construction.md, corpus-filtering.md, embedding-generation.md)
- [x] Data Records (5 file descriptions with column schemas)
- [x] Technical Validation (deduplication, relevance validation, coverage, embedding quality)
- [x] Usage Notes (reproducibility + reuse potential + limitations)
- [x] Code Availability (phase-by-phase script listing)
- [x] Data Availability (Zenodo DOI, CC BY 4.0)
- [x] No analytical results or discussion (Scientific Data constraint)
- [x] AI-tell words: 0 occurrences

## Gaps to close

### Content gaps

1. **Zenodo deposit update**: Current Zenodo deposit (10.5281/zenodo.19097045) was
   packaged for the Oeconomia submission. Need to verify it includes all 5 files
   listed in Data Records (refined_works.csv, embeddings.npz, corpus_audit.csv,
   semantic_clusters.csv, citations.csv). May need a new version.

2. **bibCNRS and SciSpace raw exports**: Data Availability section promises
   these are in the Zenodo deposit. Verify.

3. **Repository URL**: Code Availability says "[URL to be added upon acceptance]."
   Need to decide: public GitHub repo now, or upon acceptance?

4. **Nearest-neighbour spot checks**: Technical Validation claims "92% of cases"
   for nearest-neighbour coherence. This number needs to be generated from an
   actual evaluation — either run the check or remove the specific number and
   describe qualitatively.

5. **Figures**: The current draft has no figures. Scientific Data allows up to ~8.
   Consider adding:
   - Pipeline diagram (fig_dag.png exists)
   - UMAP semantic map (fig_semantic.png exists, referenced in includes)
   - Publication volume over time (fig_bars.png exists)
   - Source overlap Venn/UpSet diagram (would need creating)

6. **Author contributions statement**: Required section, not yet written.

7. **Competing interests statement**: Required section, not yet written.

8. **Acknowledgements**: Required section, not yet written.

### Formatting gaps

9. **Reference style**: Scientific Data uses Nature style (numbered, superscript).
   Current bibliography uses author-date. Need to configure Quarto CSL.

10. **Quarto template**: The `christopherkenny/scientific-data` Quarto extension
    provides the correct formatting. Consider installing it.

11. **Section numbering**: Scientific Data Data Descriptors use unnumbered sections.
    The current draft uses `##` which may or may not produce numbers depending on
    Quarto config.

### Process gaps

12. **Cover letter**: Required for submission. Should address:
    - Why this dataset is valuable to the community
    - Relationship to the Oeconomia submission
    - Multilingual design as distinctive contribution

13. **APC funding**: €2,390. Need to confirm CNRS DIST or project funding.

14. **Co-authors**: Currently single-author. Consider whether collaborators
    should be added (CIRED colleagues who contributed to teaching canon,
    grey literature curation, or code review).

## Priority order

1. Figures (high impact, existing assets)
2. Nearest-neighbour validation (verify or remove claim)
3. Zenodo deposit completeness
4. Author contributions + competing interests + acknowledgements
5. Nature CSL / Quarto template
6. Cover letter
7. Repository URL decision
8. APC funding confirmation

## Estimated effort

| Task | Effort |
|------|--------|
| Add figures + captions | 1-2 hours |
| Nearest-neighbour validation script | 1 hour |
| Zenodo deposit update | 30 min |
| Boilerplate sections | 30 min |
| Nature CSL setup | 30 min |
| Cover letter draft | 1 hour |
| **Total** | **~5-6 hours** |

## Decision points for the author

1. **Repository**: make GitHub repo public now, or wait for acceptance?
2. **Co-authors**: single-author or add contributors?
3. **APC funding source**: CNRS DIST, project budget, or fallback to
   Data Science Journal (£770)?
4. **Submission timing**: before or after Oeconomia decision?
   (Sequential: wait for acceptance → stronger cross-reference.
   Parallel: submit now → faster, but risk of conflicting reviews.)
5. **Nearest-neighbour claim**: run the validation or soften the language?
