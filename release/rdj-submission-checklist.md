# RDJ4HSS Submission Checklist

## Manuscript
- [x] Title: "A Curated Corpus of Climate Finance Literature, 1990–2024: Six Sources, Eight Languages"
- [x] Sections follow RDJ4HSS structure: Abstract, Keywords, Related dataset, 1. Introduction, 2. Method (2.1 Sources, 2.2 Data Structure, 2.3 Quality/Biases), 3. Data, 4. Concluding Remarks, Acknowledgements, References
- [ ] Word count ≤ 2,500 (body sections 1–4) — verify after final edits
- [x] Author-date citations (APA-like)
- [x] Numbered sections (1., 2., 2.1, etc.)
- [x] Related dataset with DOI before Introduction
- [x] Figure at required resolution (fig_bars.png)
- [x] Table included (tab_corpus_sources.md)

## Data deposit
- [x] Zenodo DOI: 10.5281/zenodo.19097045
- [ ] Update Zenodo deposit with v1.1 data files
- [x] CC BY 4.0 license
- [x] Suggested citation in paper
- [x] Pipeline source code on GitHub (MIT license)

## Cover letter
- [x] `release/cover-letter-rdj.txt` — addresses editors, explains scope fit
- [x] Citation count matches current data (929,014)
- [ ] Review for any other stale numbers

## Reproducibility
- [x] Analysis archive builds: `make archive-analysis`
- [ ] Checksum verification — 6/9 outputs match, 3 clustering outputs have cross-platform numerical differences (ticketed)
- [x] DVC pipeline documented
- [x] pyproject.toml pins dependencies

## Missing items
- [ ] AI disclosure statement (required?)
- [ ] Anonymized PDF for blind review (check if RDJ4HSS uses blind review)
- [ ] DMP (OPIDoR or Zenodo-hosted)
- [ ] release/release-journal.md entry for RDJ4HSS
