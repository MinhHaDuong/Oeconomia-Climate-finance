# Release & Submission Checklist

Paper: "Inventing Climate Finance. From Incremental Costs to Strategic Ambiguity"
Journal: OEconomia — History | Methodology | Philosophy
Date: _______________


## A. Build archives

- [ ] `make archive-analysis archive-manuscript`
- [ ] Extract analysis in /tmp, run `uv sync && make && make verify`
- [ ] Extract manuscript in /tmp, run `make && make verify`
- [ ] `mkdir -p release && cp climate-finance-analysis.tar.gz climate-finance-manuscript.tar.gz release/`


## B. Zenodo deposit (zenodo.org → New Upload)

- [ ] Upload `climate-finance-analysis.tar.gz`
- [ ] Upload `climate-finance-manuscript.tar.gz`
- [ ] Title: Reproducibility archives for: Inventing Climate Finance. From Incremental Costs to Strategic Ambiguity
- [ ] Authors: Minh Ha-Duong (CIRED, CNRS)
- [ ] License: CC-BY-NC-4.0
- [ ] Type: Dataset
- [ ] Keywords: climate finance, quantification, accounting categories, international organisations, reproducibility
- [ ] Description (paste):

      Two reproducibility archives for a history of economic thought study
      of climate finance, submitted to OEconomia. Both archives have been
      tested on two independent machines and ship pinned dependency lockfiles
      for exact reproduction. (1) climate-finance-analysis.tar.gz — analysis
      scripts, input data (refined corpus of ~30,000 works), and expected
      output checksums. Extract, run: uv sync && make && make verify.
      (2) climate-finance-manuscript.tar.gz — Quarto manuscript sources with
      pre-built figures. Extract, run: make && make verify.

- [ ] Related identifier: https://github.com/MinhHaDuong/Oeconomia-Climate-finance (is supplemented by)
- [ ] Reserve DOI → write it here: 10.5281/zenodo._______________
- [ ] Publish


## C. HAL deposit (hal.science)

- [ ] Upload manuscript PDF
- [ ] Upload both tarballs as annexes
- [ ] Affiliation: CIRED (UMR 8568)
- [ ] HAL ID: _______________


## D. Git

- [ ] `git tag v1.0-submission && git push origin v1.0-submission`


## E. Oeconomia submission (oeconomia-hmp.fr)

- [ ] Create account on https://oeconomia-hmp.fr/index.php/oeconomia/about/submissions
- [ ] Upload anonymized manuscript PDF (already shows [Anonymous])
- [ ] Upload figures as separate files:
  - [ ] fig_bars.png (>=1500px wide, 300 dpi)
  - [ ] fig_composition.png (>=1500px wide, 300 dpi)
- [ ] Enter metadata on OJS:
  - [ ] English abstract
  - [ ] French abstract (résumé)
  - [ ] English keywords
  - [ ] French keywords (mots-clés)
  - [ ] JEL codes: B20, Q54, F35, Q56
- [ ] Attach cover letter (from docs/submission-plan.md §1a) — fill in Zenodo DOI
- [ ] Attach AI disclosure (from docs/submission-plan.md §1b)
- [ ] Submit


## F. Final checks

- [ ] Cover letter DOI placeholder filled
- [ ] Manuscript PDF shows [Anonymous], no author info
- [ ] Manuscript PDF shows [repository URL removed for review]
- [ ] Bibliography renders ISBN/ISSN (corrected CSL)
- [ ] Figures legible in print at journal column width


Done: _______________  Submitted: _______________
