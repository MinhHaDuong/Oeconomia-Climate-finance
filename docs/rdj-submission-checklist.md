# RDJ4HSS Submission Checklist

## Manuscript
- [x] Title: "A Curated Corpus of Climate Finance Literature, 1990–2024: Six Sources, Multilingual Retrieval, and Grey Literature"
- [x] Sections follow RDJ4HSS structure: Abstract, Keywords, Related dataset, 1. Introduction, 2. Method (2.1 Sources, 2.2 Data Structure, 2.3 Quality/Biases), 3. Data, 4. Concluding Remarks, Acknowledgements, References
- [ ] Word count ≤ 2,500 (body sections 1–4) — verify after final edits
- [x] Author-date citations (APA-like)
- [x] Numbered sections (1., 2., 2.1, etc.)
- [x] Related dataset with DOI before Introduction
- [x] Figure at required resolution (fig_bars.png)
- [x] Table included (tab_corpus_sources.md)

## Data deposit
- [x] Zenodo DOI: 10.5281/zenodo.19236130
- [ ] Update Zenodo deposit with v1.1 data files
- [x] CC BY 4.0 license
- [x] Suggested citation in paper
- [x] Pipeline source code on GitHub (MIT license)

## Cover letter
- [x] Cover letter sent: `release/2026-03-26 RDJ4HSS/CoverLetter.txt`
- [x] Citation count in as-sent letter: 929,014 (v1.0 number; actual v1.1 is 968,871)
- [x] As-sent copy: `release/2026-03-26 RDJ4HSS/CoverLetter.txt`

## Reproducibility
- [x] Analysis archive builds: `make archive-analysis`
- [ ] Checksum verification — 6/9 outputs match, 3 clustering outputs have cross-platform numerical differences (ticketed)
- [x] DVC pipeline documented
- [x] pyproject.toml pins dependencies

## Questions for author before submission
- [ ] Does RDJ4HSS use blind review? (website unclear — check submission form)
- [ ] AI disclosure: not mentioned in guidelines, but good practice to include
- [ ] Word count scope: 2,500 limit applies to which sections? (body ~2,341)

## Post-submission
- [ ] Deposit DMP on OPIDoR (`docs/data-management-plan.md`)

## Done
- [x] DMP updated with v1.1 numbers (`docs/data-management-plan.md`)
- [x] release/release-journal.md entry for RDJ4HSS
- [x] ESHET-HES slides outline (`docs/eshet-hes-slides-outline.md`)
