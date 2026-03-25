# Data paper reproducibility archive

Companion to: Ha-Duong M. (2026) "A Multilingual Corpus of Climate Finance
Literature, 1990–2024", Research Data Journal for the Humanities and Social
Sciences.

Dataset DOI: [10.5281/zenodo.19097045](https://doi.org/10.5281/zenodo.19097045)

## What this archive contains

| Path | Description |
|------|-------------|
| `data/catalogs/` | Pre-built corpus outputs (refined_works.csv, embeddings.npz, citations.csv, corpus_audit.csv) |
| `data/exports/` | Pre-harvested bibCNRS and SciSpace exports (require institutional credentials to re-collect) |
| `scripts/` | All pipeline scripts (discovery, merge, enrichment, refinement, embedding) |
| `config/` | Query taxonomy, refinement rules, source configuration |
| `tests/` | Acceptance tests and quality checks |
| `Makefile` | Full pipeline targets |
| `Makefile.datapaper` | Verification targets (this archive) |
| `Dockerfile` | Container build for isolated reproduction |
| `checksums-data.md5` | MD5 checksums of all shipped data files |
| `verify_corpus.py` | Structural comparison script (Level 2 verification) |
| `TOOLCHAIN.txt` | Python, uv, and key package versions used for the build |

## Two-level verification

### Level 1: Checksum verification (fast, offline)

Verifies that shipped data files are bitwise identical to the author's outputs.
No Python, no network, no API keys needed.

```bash
tar xzf climate-finance-datapaper.tar.gz
cd climate-finance-datapaper
make -f Makefile.datapaper verify-quick
```

### Level 2: Full rebuild (slow, requires internet)

Rebuilds the corpus from source APIs and compares against the shipped
reference. Takes 4–6 hours. Exact byte-identity is not expected because
API responses evolve (new publications, updated citation counts). Instead,
the comparison checks structural equivalence: schema, row-count tolerance
(±5%), and statistical similarity of key metrics.

```bash
# Option A: native (requires Python >= 3.10 and uv)
make -f Makefile.datapaper verify-rebuild

# Option B: Docker (isolated, no local Python needed)
docker build -t climate-finance-corpus .
docker run -v $(pwd)/rebuilt:/app/data climate-finance-corpus
# Then compare rebuilt/ against data/catalogs/
```

## API keys and credentials

| Source | Key required? | How to obtain |
|--------|--------------|---------------|
| OpenAlex | Optional (faster with Premium key) | [openalex.org/pricing](https://openalex.org/pricing) |
| ISTEX | No | Public API |
| World Bank | No | Public API |
| Crossref | No (polite pool recommended) | Set `mailto` in config |
| bibCNRS | Pre-harvested (CNRS Janus credentials) | Included in `data/exports/` |
| SciSpace | Pre-harvested (commercial tool) | Included in `data/exports/` |

## Non-reproducible steps

- bibCNRS and SciSpace raw exports cannot be re-harvested without institutional
  credentials. Their exports are included in `data/exports/` for this reason.
- Citation counts from OpenAlex change daily. The shipped corpus reflects
  counts as of the harvest date recorded in `TOOLCHAIN.txt`.
- The LLM audit (Phase C2) requires an OpenRouter API key and is non-deterministic.
  It can be skipped with `--skip-llm`; the shipped `llm_audit.csv` serves as the
  reference.

## Pipeline phases

```
Phase 1 — Corpus building (this archive):
  make corpus-discover   # harvest from 6 sources (~2 hours)
  make corpus-enrich     # DOIs, abstracts, citations (~3 hours)
  make corpus-extend     # compute 6 quality flags
  make corpus-filter     # apply retention policy → refined_works.csv
  make corpus-align      # align embeddings and citations to filtered corpus

Phase 2 — Analysis (separate):
  make figures           # UMAP, clustering, breakpoints

Phase 3 — Rendering (separate):
  make manuscript        # Quarto → PDF
```
