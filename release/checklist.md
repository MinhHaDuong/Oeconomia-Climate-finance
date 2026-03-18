# Release & Submission Checklist

Paper: "Inventing Climate Finance. From Incremental Costs to Strategic Ambiguity"
Journal: OEconomia — History | Methodology | Philosophy
Date: 2026-03-18


## A. Build archives

- [x] `make archive-analysis archive-manuscript`
- [x] Extract analysis in /tmp, run `uv sync && make && make verify`
- [x] Extract manuscript in /tmp, run `make && make verify`
- [x] `mkdir -p release && cp climate-finance-analysis.tar.gz climate-finance-manuscript.tar.gz release/`


## B. Zenodo deposit (zenodo.org → New Upload)

- [x] Upload `climate-finance-analysis.tar.gz`
- [x] Upload `climate-finance-manuscript.tar.gz`
- [x] Title: Reproducibility archives for: Inventing Climate Finance. From Incremental Costs to Strategic Ambiguity
- [x] Authors: Minh Ha-Duong (CIRED, CNRS)
- [x] License: CC-BY-NC-4.0
- [x] Type: Dataset
- [x] Keywords: climate finance, quantification, accounting categories, international organisations, reproducibility
- [x] Description (paste):

      Two reproducibility archives for a history of economic thought study
      of climate finance, submitted to OEconomia. Both archives have been
      tested on two independent machines and ship pinned dependency lockfiles
      for exact reproduction. (1) climate-finance-analysis.tar.gz — analysis
      scripts, input data (refined corpus of ~30,000 works), and expected
      output checksums. Extract, run: uv sync && make && make verify.
      (2) climate-finance-manuscript.tar.gz — Quarto manuscript sources with
      pre-built figures. Extract, run: make && make verify.

- [x] Related identifier: https://github.com/MinhHaDuong/Oeconomia-Climate-finance (is supplemented by)
- [x] Reserve DOI → write it here: . https://doi.org/10.5281/zenodo.19097045
- [x] Publish


## C. HAL deposit (hal.science)

- [x] Upload manuscript PDF
- [x] Upload both tarballs as annexes (pas fait: déja sur Zenodo)
- [x] Affiliation: CIRED (UMR 8568)
- [x] HAL ID: hal-05558422v1


## D. Git

- [x] `git tag v1.0-submission && git push origin v1.0-submission`


## E. Oeconomia submission (oeconomia-hmp.fr)

- [x] Create account on https://oeconomia-hmp.fr/index.php/oeconomia/about/submissions
- [x] Upload anonymized manuscript PDF (already shows [Anonymous])
- [x] Upload figures as separate files:
  - [x] fig_bars.png (>=1500px wide, 300 dpi)
  - [x] fig_composition.png (>=1500px wide, 300 dpi)
- [x] Enter metadata on OJS:
  - [x] English abstract
  - [x] French abstract (résumé)
  - [x] English keywords
  - [x] French keywords (mots-clés)
  - [x] JEL codes: B20, Q54, F35, Q56
- [x] Attach cover letter (from docs/submission-plan.md §1a) — fill in Zenodo DOI
- [x] Attach AI disclosure (from docs/submission-plan.md §1b)
- [x] Submit


## F. Final checks

- [x] Cover letter DOI placeholder filled
- [x] Manuscript PDF shows [Anonymous], no author info
- [x] Manuscript PDF shows [repository URL removed for review]
- [x] Bibliography renders ISBN/ISSN (corrected CSL)
- [x] Figures legible in print at journal column width


Done: 2026-03-18  Submitted: 2026-03-18
