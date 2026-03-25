# Submission readiness — pre-sprout gate

Run this checklist before creating a submission branch (`runbooks/submission-branch.md`).
Every item must pass. If one fails, fix it before sprouting.

## Build

- [ ] Paper builds cleanly: e.g., `make output/content/manuscript.pdf`
- [ ] Full test suite passes: `make check`
- [ ] No warnings or missing references in the build log

## Data freeze

- [ ] Computed variables pinned in `content/{document}-vars.yml`
- [ ] Reference data snapshots saved in `config/` (e.g., `config/v1_*` files)
- [ ] Manuscript decoupled from live corpus — re-running `dvc repro` does not change the paper
- [ ] Provenance column links current corpus rows to the frozen version

## Reproducibility

- [ ] Reproducibility archive(s) built (code tarball + data tarball)
- [ ] Archive tested on a second machine — builds from scratch, produces identical output
- [ ] Zenodo deposit created (or deposit plan documented with target DOI)
- [ ] HAL deposit created (or planned)

## Submission artifacts

- [ ] Cover letter in `release/`
- [ ] AI disclosure statement in `release/`
- [ ] Journal-specific files prepared (anonymized PDF, figures at required resolution, metadata)
- [ ] `release/release-journal.md` entry drafted

## Prior art

The v1.0 Oeconomia submission established this pattern:
- Frozen `config/v1_cluster_labels.json`, `config/v1_tab_alluvial.csv`, `config/v1_identifiers.txt.gz`
- Pinned `content/manuscript-vars.yml`
- Zenodo tarballs (analysis 56 MB + manuscript 683 KB), tested on two independent machines
- `release/2026-03-18 Oeconomia/` with cover letter, AI disclosure, anonymized PDF
