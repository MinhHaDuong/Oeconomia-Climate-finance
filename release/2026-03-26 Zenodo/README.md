## Zenodo deposit: Data paper (RDJ4HSS)

- Zenodo DOI: 10.5281/zenodo.19236130
- Repository: https://github.com/MinhHaDuong/Oeconomia-Climate-finance
- Git tag: v1.1-rdj-submitted (to be created at freeze)
- Submission branch: submission/rdj-data-paper (to be sprouted from tag)

### Archive

Single archive: **climate-finance-datapaper.tar.gz**

Built by `make archive-datapaper`. Contains:

- `code/` — full pipeline source (git archive of HEAD), plus pre-built
  figures and tables for rendering. Includes `Makefile.datapaper` with
  three targets: `make verify`, `make papers`, `make corpus`.
- `data/` — v1.1 deposit files: climate_finance_corpus.csv (abstracts
  stripped), embeddings.npz, citations.csv, per-source catalogs.
