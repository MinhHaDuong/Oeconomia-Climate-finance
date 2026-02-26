# Technical Note: Literature Corpus Construction

**Date:** 2026-02-23
**Project:** How Climate Finance Became an Economic Object (Œconomia submission)
**Purpose:** Full reproducibility documentation for the multi-source literature corpus

---

## 1. Overview

The corpus assembles academic and grey literature on climate finance from six sources into a unified, deduplicated catalog of 12,372 works with 232,218 citation links. All scripts are in `scripts/`, all outputs in `data/catalogs/` (gitignored; reproducible from scripts).

### Pipeline summary

```
ISTEX (local JSON) ──→ istex_works.csv (482)
                       istex_refs.csv (19,744)

OpenAlex API ─────────→ openalex_works.csv (11,313)

bibCNRS (manual RIS) ─→ bibcnrs_works.csv (242)

SciSpace (AI reports) → scispsace_works.csv (663)

Grey (YAML + WB API) ─→ grey_works.csv (213)

All *_works.csv ──────→ unified_works.csv (12,372)   ← catalog_merge.py
                         ↓
Crossref API ─────────→ citations.csv (232,218)       ← enrich_citations.py
```

## 2. Sources and queries

### 2.1 ISTEX (482 works, 19,744 cited references)

- **Source:** ISTEX national archive (https://www.istex.fr/)
- **Query:** `"climate finance" OR "finance climat" OR "finance climatique"`
- **Date:** Corpus downloaded 2026-02 (exact date in corpus metadata)
- **Method:** Full-text PDF corpus with JSON metadata, stored locally in `data/raw/` (symlinked, read-only)
- **Script:** `scripts/catalog_istex.py` — parses all `data/raw/*/*.json` files
- **Known issues:**
  - DOI stored as list in ISTEX JSON (not string) — handled in parser
  - Temporal cliff after 2016 due to archival licensing (86 articles in 2016 → 9 in 2017)
  - Publisher bias: 66% Elsevier + Wiley; Taylor & Francis: 1; Sage: 2
  - Affiliations field occasionally contains `None` values — filtered
- **Output:** `data/catalogs/istex_works.csv`, `data/catalogs/istex_refs.csv`

### 2.2 OpenAlex (11,313 works)

- **Source:** OpenAlex API (https://api.openalex.org/)
- **Query:** Two cursor-paginated passes:
  1. `filter=default.search:"climate finance"`
  2. `filter=default.search:"finance climat"` (also captures "finance climatique")
- **Date:** 2026-02-23
- **Method:** Cursor pagination, polite pool (mailto: minh.haduong@cnrs.fr), 0.1s delay between requests. Abstracts reconstructed from OpenAlex inverted index format. Checkpoint every 2,000 records to `.openalex_checkpoint.jsonl`.
- **Script:** `scripts/catalog_openalex.py`
- **Coverage:** 3,281 journals, years 1969–2026
- **Known issues:**
  - `default.search` may include false positives (articles mentioning "climate" and "finance" separately)
  - Under-represents non-English literature: French (92), Chinese (13), Japanese (29), German (40)
  - No full-text access (metadata + abstract only)
- **Output:** `data/catalogs/openalex_works.csv`

### 2.3 bibCNRS (242 works after deduplication)

- **Source:** bibCNRS portal (https://bib.cnrs.fr/), requires CNRS Janus credentials
- **Databases queried:** All available (aggregates WoS, EconLit, FRANCIS, PASCAL, NDL Online, HyRead)
- **Queries (title field, run 2026-02-23):**

| Query | Target language | Raw results | After dedup |
|-------|----------------|-------------|-------------|
| `TI "finance climat" OR TI "finance climatique"` | French | ~332 | 72 |
| `TI 气候融资 OR TI 气候金融` | Chinese | 80 | 76 |
| `TI 気候金融 OR TI グリーンファイナンス OR TI 気候ファイナンス` | Japanese | 43 | 41 |
| (included in French export lots) | German | 24 | 7 |
| (English-language results in above queries) | English | — | 46 |
| **Total** | | **~455** | **242** |

- **Export method:** Manual RIS export in batches of 100 (bibCNRS UI limit). Files saved to `data/exports/`.
- **Deduplication:** Title-based within bibCNRS exports (overlapping batches due to unstable result counts in bibCNRS portal). 105 duplicates removed (347 → 242).
- **Script:** `scripts/catalog_bibcnrs.py` — parses RIS format, deduplicates by normalized title
- **Known issues:**
  - bibCNRS result counts fluctuate between queries (index refresh, session state)
  - No API available; manual export only
  - 63 entries are NEWS type (press clippings), limited academic value
  - Chinese results are predominantly Taiwanese (HyRead Journal); mainland CNKI literature not covered
  - Only 34/242 entries have DOIs
- **Files in `data/exports/`:**
  - `bibcnrs_fr_1.ris`, `bibcnrs_fr_2.ris` (French, 2 lots)
  - `bibcnrs_de.ris` (German, 1 lot)
  - `bibcnrs_zh.ris` (Chinese, 1 lot)
  - `bibcnrs_ja.ris` (Japanese, 1 lot)
- **Output:** `data/catalogs/bibcnrs_works.csv`

### 2.4 Grey literature (213 works)

- **Sources:**
  1. **Curated seed list** (`data/grey_sources.yaml`): 16 entries manually selected — OECD DAC reports, UNFCCC SCF Biennial Assessments (2014–2022), Stern Review, Stern & Romani HLPF 2010, CPI Global Landscape reports (2011–2023), Kaul (1999, 2013) on global public goods, World Bank WDR 2010.
  2. **World Bank Open Knowledge Repository API** (https://openknowledge.worldbank.org/): DSpace 7 REST API, query `"climate finance"`, first 200 results.
- **Date:** 2026-02-23
- **Script:** `scripts/catalog_grey.py`
- **Known issues:**
  - World Bank API metadata uses Dublin Core in nested dict structure (not flat list) — parser handles both formats
  - OECD iLibrary and UNFCCC document repositories have no bulk API; seed file is manually curated
  - 200-item cap on World Bank results (API returns ~700 total)
- **Output:** `data/catalogs/grey_works.csv`

## 3. Merging and deduplication

- **Script:** `scripts/catalog_merge.py`
- **Method:**
  1. Load all `data/catalogs/*_works.csv` (excluding `unified_works.csv`)
  2. **Pass 1 — DOI-based dedup:** Normalize DOIs (lowercase, strip URL prefix), group by DOI, merge duplicates using source priority: openalex > scopus > istex > jstor > bibcnrs > grey
  3. **Pass 2 — Title+year dedup:** For records without DOI, normalize title (lowercase, strip punctuation), group by (title, year), merge duplicates
  4. For merged groups: concatenate sources (e.g. `openalex|istex`), take max `cited_by_count`, pick best non-empty value per field following source priority
  5. Sort by year descending, then cited_by_count descending
- **Result:** 12,055 unique works (138 appearing in 2+ sources, 9 bibCNRS entries matched OpenAlex via DOI)
- **Output:** `data/catalogs/unified_works.csv`

## 4. Citation enrichment

- **Source:** Crossref API (https://api.crossref.org/)
- **Method:** For each DOI in unified catalog, GET `https://api.crossref.org/works/{doi}` with mailto parameter (polite pool). Extract `reference` list and update `is-referenced-by-count`. 0.1s delay between requests.
- **Script:** `scripts/enrich_citations.py`
- **Checkpoint:** Every 100 DOIs to `.citations_checkpoint.jsonl`. Supports `--resume` flag.
- **Run history:**
  - First run: processed ~5,500 DOIs, interrupted by transient DNS failure
  - Second run (`--resume`): completed remaining DOIs
  - Post-processing: deduplicated 315,291 → 232,218 rows (removed 83,073 duplicates from checkpoint overlap)
- **Result:** 232,218 citation links from 4,710 source DOIs (5,637 DOIs returned 404 from Crossref — no deposited references)
- **Output:** `data/catalogs/citations.csv`

## 5. Unified CSV schema

**Works** (`*_works.csv`):
```
source, source_id, doi, title, first_author, all_authors, year, journal,
abstract, language, keywords, categories, cited_by_count, affiliations
```

**References** (`istex_refs.csv`, `citations.csv`):
```
source_doi, source_id, ref_doi, ref_title, ref_first_author,
ref_year, ref_journal, ref_raw
```

## 5b. SciSpace AI-curated corpus (663 works after dedup)

- **Source:** Two SciSpace research sessions, stored in `AI tech reports/`
- **Files parsed:**
  1. `AI tech reports/SciSpace 2/cites_2026-02-23:10:50:37_export.ris` — 20 curated entries (RIS format with DOI, abstract, AI-generated insights in N1 field)
  2. `AI tech reports/SciSpace 1/combined_climate_finance_primary_research.csv` — 334 entries (primary research compilation with thematic classification)
  3. `AI tech reports/SciSpace 1/paper_table_systematic-li_aCaEsV.csv` — 425 entries (systematic literature review extraction)
- **Query context:** SciSpace was prompted to assemble a corpus for "history of economic thought on climate finance" with emphasis on welfare/efficiency vs. political-economy orientations, key figures (Nordhaus, Stern, Corfee-Morlot, Michaelowa, Weikmans/Roberts, Kaul), and accounting categories.
- **Script:** `scripts/catalog_scispsace.py`
- **Deduplication:** 779 raw records → 663 after title-based dedup (116 duplicates across files)
- **DOI coverage:** 530/663 entries have DOIs (80%)
- **Merge result:** 346 matched existing OpenAlex entries via DOI, 317 net additions to unified catalog
- **Known issues:**
  - AI-curated metadata may contain errors (hallucinated DOIs, approximate author names)
  - Lowest merge priority — primary API sources (OpenAlex) preferred for field values
  - Thematic classifications are AI-generated, not standardized vocabulary
  - 28 additional thematic CSVs in SciSpace 1 excluded (subsets of combined CSV, would add only duplicates)
  - `SciSpace 2/cites_*_export.csv` (5221 lines) excluded — has title+authors but no DOI/year; mostly AI-generated analysis text
- **Output:** `data/catalogs/scispsace_works.csv`

## 6. Language coverage assessment

OpenAlex language distribution (11,313 works):

| Language | OpenAlex | bibCNRS addition | Assessment |
|----------|----------|-----------------|------------|
| English | 10,354 | 46 | Comprehensive |
| French | 92 | 72 | Significant gap partially filled |
| Spanish | 88 | — | Small gap, mostly applied/case studies |
| Portuguese | 45 | — | Small gap, mostly Brazilian case studies |
| German | 40 (+90 via "Klimafinanzierung") | 7 | Adequately covered |
| Chinese | 13 | 76 (mostly Taiwanese) | Major gap — mainland CNKI inaccessible |
| Japanese | 29 | 41 | Gap partially filled |
| Other | 152 | — | Turkish (28), Arabic (21), Russian (18)... |

**Uncovered territory:** Chinese-language literature in CNKI (China National Knowledge Infrastructure) is the largest known gap. OpenAlex indexes only ~13 works for 气候金融/气候融资; bibCNRS adds 76 (predominantly Taiwanese sources via HyRead). CNKI likely contains thousands of works on 绿色金融 (green finance) but has no open API and requires institutional subscription.

## 7. Retired sources

`scripts/catalog_scopus.py` and `scripts/catalog_jstor.py` were written but excluded from the active workflow. OpenAlex already indexes Scopus and JSTOR content; the marginal gain does not justify the credential setup (Elsevier API key for Scopus, Constellate/JSTOR account for JSTOR).

## 8. Requirements and reproduction

### Software
- Python 3.10+
- Dependencies: `pandas`, `requests`, `pyyaml`

### To reproduce from scratch
```bash
# 1. Parse ISTEX corpus (requires data/raw/ symlink to ISTEX JSON files)
python3 scripts/catalog_istex.py

# 2. Query OpenAlex (free, ~15 min, ~11K works)
python3 scripts/catalog_openalex.py

# 3. Parse bibCNRS exports (requires RIS files in data/exports/)
python3 scripts/catalog_bibcnrs.py

# 4. Parse SciSpace AI-curated corpus (local files in AI tech reports/)
python3 scripts/catalog_scispsace.py

# 5. Build grey literature catalog (free World Bank API, ~2 min)
python3 scripts/catalog_grey.py

# 6. Merge all catalogs
python3 scripts/catalog_merge.py

# 7. Enrich with Crossref citations (~3-4 hours for ~10K DOIs)
python3 scripts/enrich_citations.py
```

### Non-reproducible steps
- **ISTEX corpus download:** Requires ISTEX institutional access (data/raw/ is a read-only symlink)
- **bibCNRS export:** Requires CNRS Janus credentials and manual browser export from https://bib.cnrs.fr/
- **Crossref timing:** Results may vary slightly due to Crossref index updates and API availability

## 9. Bibliometric analysis

Three complementary analyses map the intellectual structure of the corpus.

### 9.1 Temporal analysis (`scripts/analyze_temporal.py`)

- **Figure 1** (`figures/fig1_emergence.pdf`): Publication counts by year (1990–2025), annotated with key COP events (Rio 1992, Copenhagen 2009, Paris 2015, Glasgow 2021, Baku 2024 NCQG).
- **Table 1** (`tables/tab1_terms.csv`): First appearance and growth of 16 key concepts in abstracts, tracked via regex on the 9,757 abstracts in the 1990–2025 window. Terms include both efficiency/leverage vocabulary ("leverage" first: 2009, "blended finance": 2014) and accountability/equity vocabulary ("additionality": 1994, "grant-equivalent": 2017, "NCQG": 2022).
- **Bonus:** `tables/language_by_year.csv` — language distribution over time.

### 9.2 Co-citation analysis (`scripts/analyze_cocitation.py`)

- **Method:** Co-citation analysis (Small 1973, White & Griffith 1981). Two works are connected when they appear together in the same reference list. From the 232,218 citation links (4,710 source papers), a co-citation matrix is built for the 200 most-cited references. Community detection uses the Louvain algorithm (Blondel et al. 2008) on a weighted network (edges = co-citation count ≥ 3).
- **Result:** 200 nodes, 3,234 edges, 6 communities detected:
  - Community 0 (5): Health/adaptation periphery
  - Community 1 (40): **Financial economics** — climate risk, ESG (Krueger, Hong, Giglio, Bolton)
  - Community 2 (45): **Green finance instruments** — green bonds (Banga, Zhang, Taghizadeh-Hesary)
  - Community 3 (48): **Political economy** — accounting disputes, justice (Weikmans, Campiglio, Keohane, Ciplet)
  - Community 4 (51): **Climate finance governance** — policy reviews (Bhandary, Roberts, Bracking)
  - Community 5 (11): Nature-based solutions (Griscom, Steffen, Rockström)
- **Figure 2** (`figures/fig2_communities.pdf`): Spring-layout network, node size ∝ √citations, color = community.
- **Outputs:** `data/catalogs/communities.csv`, `tables/tab2_community_summary.csv`

### 9.3 Semantic landscape (`scripts/analyze_embeddings.py`)

- **Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers, 12-layer multilingual BERT, 384-dim). Chosen for multilingual support (50+ languages) to place EN/FR/ZH/JA/DE abstracts in a shared semantic space.
- **Embeddings:** 9,653 abstracts encoded (batch size 256, ~6 min on CPU). Cached in `data/catalogs/embeddings.npy` (14.8 MB, 9653 × 384 float32).
- **Projection:** UMAP (n_neighbors=15, min_dist=0.05, cosine metric, seed=42).
- **Clustering:** KMeans (k=6, matching co-citation community count). Six semantic clusters identified:
  - Cluster 0 (1,988): Climate policy & governance
  - Cluster 1 (1,761): Energy & engineering
  - Cluster 2 (1,911): Finance & ESG
  - Cluster 3 (1,433): Environment & agriculture
  - Cluster 4 (2,511): Climate finance *sensu stricto*
  - Cluster 5 (49): Outliers
- **Cross-validation:** 48 works matched between co-citation communities and semantic clusters. Co-citation communities 3 (political economy) and 4 (governance) concentrate in semantic cluster 4 (31/48 matches), confirming convergence between citation behavior and discourse content.
- **Figures:**
  - `fig3_semantic.pdf` — colored by semantic cluster
  - `fig3_semantic_lang.pdf` — non-English works highlighted (shows multilingual integration in semantic space)
  - `fig3_semantic_period.pdf` — colored by article periodization (1990–2008, 2009–2015, 2016–2021, 2022–2025)
- **Outputs:** `data/catalogs/semantic_clusters.csv`, `data/catalogs/embeddings.npy`

### 9.4 Dependencies

Analysis scripts require additional packages beyond the corpus pipeline:
```
networkx, python-louvain, sentence-transformers, torch (CPU),
umap-learn, hdbscan, matplotlib, seaborn, scikit-learn
```
All managed via `pyproject.toml` + `uv sync`.

### 9.5 Reproduction

```bash
# After corpus is built (steps 1-7 above):
cd scripts

# Figure 1 + Table 1 (fast, ~5s)
uv run python analyze_temporal.py

# Figure 2: co-citation network (~30s)
uv run python analyze_cocitation.py

# Figure 3: semantic landscape (~7 min on CPU, cached after first run)
uv run python analyze_embeddings.py
```

## 10. File inventory

### Corpus data

| File | Rows | Size | Reproducible |
|------|------|------|-------------|
| `catalogs/istex_works.csv` | 482 | ~0.5 MB | Yes (from local JSON) |
| `catalogs/istex_refs.csv` | 19,744 | ~2 MB | Yes (from local JSON) |
| `catalogs/openalex_works.csv` | 11,313 | ~12 MB | Yes (API, free) |
| `catalogs/bibcnrs_works.csv` | 242 | ~0.1 MB | Partially (needs manual export) |
| `catalogs/scispsace_works.csv` | 663 | ~0.8 MB | Yes (from local AI tech reports) |
| `catalogs/grey_works.csv` | 213 | ~0.2 MB | Yes (API + YAML seed) |
| `catalogs/unified_works.csv` | 12,372 | ~14 MB | Yes (merge script) |
| `catalogs/citations.csv` | 232,218 | ~25 MB | Yes (API, ~4 hours) |
| `exports/*.ris` | 5 files | ~155 KB | Archived (manual bibCNRS export) |
| `grey_sources.yaml` | 16 entries | ~3 KB | Curated (version-controlled) |

### Analysis outputs

| File | Description | Reproducible |
|------|-------------|-------------|
| `figures/fig1_emergence.pdf` | Publication timeline 1990–2025 | Yes |
| `figures/fig2_communities.pdf` | Co-citation network (6 communities) | Yes |
| `figures/fig3_semantic.pdf` | Semantic landscape (6 clusters) | Yes |
| `figures/fig3_semantic_lang.pdf` | Same, colored by language | Yes |
| `figures/fig3_semantic_period.pdf` | Same, colored by period | Yes |
| `tables/tab1_terms.csv` | Key concept emergence (16 terms) | Yes |
| `tables/tab2_community_summary.csv` | Top works per co-citation community | Yes |
| `tables/language_by_year.csv` | Language distribution by year | Yes |
| `catalogs/communities.csv` | Co-citation community assignments (200 works) | Yes |
| `catalogs/semantic_clusters.csv` | Semantic cluster assignments (9,653 works) | Yes |
| `catalogs/embeddings.npy` | Abstract embeddings (9,653 × 384) | Yes (cached) |
