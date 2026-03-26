# Data paper reproducibility archive

Companion to: Ha-Duong M. (2026) "A Curated Corpus of Climate Finance
Literature, 1990–2024: Six Sources, Multilingual Retrieval, and Grey
Literature", Research Data Journal for the Humanities and Social Sciences.

Dataset DOI: [10.5281/zenodo.19236130](https://doi.org/10.5281/zenodo.19236130)

## Archive structure

```
climate-finance-datapaper/
  code/                    # Pipeline source + data paper
    Makefile               # Three targets: test, papers, corpus
    content/               # Data paper qmd, vars, bibliography, figures
    scripts/               # All pipeline scripts
    config/                # Query taxonomy, source configuration
    dvc.yaml, dvc.lock     # Pipeline definitions
    checksums-data.md5     # Reference checksums for data/
    .env                   # Points CLIMATE_FINANCE_DATA=../data
  data/                    # Deposit files
    climate_finance_corpus.csv   # Full corpus (abstracts stripped)
    embeddings.npz               # Multilingual sentence-transformer vectors
    citations.csv                # Citation network
    *_works.csv                  # Per-source catalogs
```

## Three targets

### `make test` — verify data checksums (fast, offline)

Checks that shipped data files match the author's checksums.
No Python, no internet needed.

```bash
tar xzf climate-finance-datapaper.tar.gz
cd climate-finance-datapaper/code
make test
```

### `make papers` — render the data paper (fast, needs Quarto)

Renders `data-paper.pdf` from frozen variables and pre-built figures.
No pipeline, no API calls, no corpus data needed.

```bash
make papers
# Output: output/content/data-paper.pdf
```

Prerequisites: [Quarto](https://quarto.org/docs/get-started/), XeLaTeX.

### `make corpus` — rebuild the corpus (slow, needs internet)

Runs the full DVC pipeline incrementally. Uses caches in `enrich_cache/`
so only new or changed data is fetched from APIs.

```bash
make corpus
```

Prerequisites: Python >= 3.10, [uv](https://docs.astral.sh/uv/).
Takes 4–6 hours on first run. Subsequent runs are incremental.

## API keys

| Source | Key needed? | Notes |
|--------|-------------|-------|
| OpenAlex | Optional | Premium key in `.env` for faster harvest |
| ISTEX | No | Public API |
| World Bank | No | Public API |
| Crossref | No | Polite pool (set `mailto` in config) |
| bibCNRS | Pre-harvested | Source catalog included in `data/` |
| SciSpace | Pre-harvested | Source catalog included in `data/` |

## Non-reproducible aspects

- bibCNRS and SciSpace cannot be re-harvested without institutional credentials.
  Their source catalogs are included in `data/`.
- Citation counts change daily. The shipped corpus reflects counts as of the
  harvest date.
- API responses may include publications added after the harvest date, so
  exact byte-identity is not expected on rebuild.
