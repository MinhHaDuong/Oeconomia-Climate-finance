# Literature Indexing Pipeline

Built 2026-02-23. Multi-source catalog of academic and grey literature on climate finance, supporting the Oeconomia HET manuscript.

## Data location

Generated data (catalogs, exports, syllabi, embeddings) is stored **outside** the
repository at:

    ~/data/projets/Oeconomia-Climate-finance/

This path is configured in `scripts/utils.py` (`DATA_DIR`) and can be overridden
with the `CLIMATE_FINANCE_DATA` environment variable. Only configuration files
(`grey_sources.yaml`, `teaching_sources.yaml`, `het_core.csv`) and documentation
are tracked in this directory.

## Data inventory

| File | Rows | Description |
|------|------|-------------|
| `catalogs/istex_works.csv` | 482 | ISTEX corpus (local JSON metadata) |
| `catalogs/istex_refs.csv` | 19,744 | Cited references extracted from ISTEX articles |
| `catalogs/openalex_works.csv` | 11,313 | OpenAlex API query (free, no auth) |
| `catalogs/bibcnrs_works.csv` | 242 | bibCNRS exports: French, Chinese, Japanese, German (deduplicated) |
| `catalogs/scispsace_works.csv` | 663 | SciSpace AI-curated corpus (RIS + CSV, deduplicated) |
| `catalogs/grey_works.csv` | 213 | 16 curated seed entries + 200 World Bank OKR API |
| `catalogs/unified_works.csv` | 12,372 | Deduplicated merge of all sources (474 multi-source) |
| `catalogs/citations.csv` | 232,218 | Crossref citation links (176K with DOIs, from 4,710 source DOIs, deduplicated) |
| `grey_sources.yaml` | 16 | Curated seed list (OECD, UNFCCC SCF, CPI, Stern, Kaul) |

## Coverage vs. ISTEX alone

The ISTEX corpus had two major gaps:
- **Temporal cliff after 2016** (archival licenses: 86 articles in 2016, then 9 in 2017)
- **Publisher bias** (66% Elsevier+Wiley; Taylor & Francis: 1, Sage: 2)

OpenAlex extends coverage to 11,313 works across 3,281 journals from 1969-2026, filling post-2016 literature and underrepresented publishers.

## CSV schema

**Works** (`*_works.csv`):
`source, source_id, doi, title, first_author, all_authors, year, journal, abstract, language, keywords, categories, cited_by_count, affiliations`

**References** (`istex_refs.csv`, `citations.csv`):
`source_doi, source_id, ref_doi, ref_title, ref_first_author, ref_year, ref_journal, ref_raw`

## Scripts (in `scripts/`)

| Script | Source | Auth required |
|--------|--------|---------------|
| `utils.py` | Shared helpers | - |
| `catalog_istex.py` | Local JSON files | No |
| `catalog_openalex.py` | OpenAlex API | No (free, polite pool) |
| `catalog_grey.py` | YAML seed + World Bank OKR API | No |
| `catalog_bibcnrs.py` | bibCNRS RIS exports | Yes (CNRS Janus) |
| `catalog_scispsace.py` | SciSpace AI tech reports | No (local files) |
| `catalog_merge.py` | Merges all `*_works.csv` | No |
| `enrich_citations.py` | Crossref API | No (polite pool) |

### Retired scripts

`catalog_scopus.py` and `catalog_jstor.py` were written but are not part of the active workflow. OpenAlex (11,313 works, 3,281 journals, 1969-2026) already indexes Scopus and JSTOR content. The marginal gain from querying these sources directly does not justify the credential setup (Elsevier API key for Scopus, Constellate account for JSTOR).

### bibCNRS: non-English complement

OpenAlex under-represents non-English literature. bibCNRS (aggregating WoS, EconLit, FRANCIS, NDL Online, HyRead) fills the gaps. Three queries were run (2026-02-23):

| Query | Language | bibCNRS results | After dedup |
|-------|----------|-----------------|-------------|
| `TI "finance climat" OR TI "finance climatique"` | French | ~332 | 72 |
| `TI 气候融资 OR TI 气候金融` | Chinese | 80 | 76 |
| `TI 気候金融 OR TI グリーンファイナンス OR TI 気候ファイナンス` | Japanese | 43 | 41 |
| (from French lots) | German | 24 | 7 |
| (English titles in results) | English | — | 46 |
| **Total** | | **~455** | **242** |

Export as RIS in batches of 100 to `data/exports/`, then run `catalog_bibcnrs.py`. After merge, 233 entries are net additions to the unified catalog (9 already matched OpenAlex via DOI).

### SciSpace: AI-curated HET corpus

Two SciSpace research sessions produced a targeted corpus for the HET analysis. Parsed from `AI tech reports/SciSpace 1/` (CSVs: combined primary research + systematic review paper table) and `AI tech reports/SciSpace 2/` (RIS export). 663 unique entries after internal dedup; 346 matched existing OpenAlex entries via DOI, 317 net additions. Lowest merge priority (AI-curated metadata less reliable than primary API sources).

## How to re-run

1. **Re-merge after changes**: `python3 scripts/catalog_merge.py`
2. **Refresh OpenAlex**: `python3 scripts/catalog_openalex.py`
3. **Update grey literature**: edit `data/grey_sources.yaml`, run `python3 scripts/catalog_grey.py`
4. **Add bibCNRS exports**: save RIS files to `data/exports/`, run `python3 scripts/catalog_bibcnrs.py`, then re-merge

## Query used

All sources searched for: `"climate finance" OR "finance climat" OR "finance climatique"`

## Known limitations

- Crossref enrichment resolved 4,710/10,347 DOIs (rest returned 404 from Crossref)
- Many DOIs (especially newer, non-journal) return 404 from Crossref (no deposited references)
- Grey literature coverage is partial: OECD iLibrary and UNFCCC have no bulk API, seed file is manually curated
- OpenAlex `default.search` may include some false positives (articles about "climate" and "finance" separately)
- OpenAlex under-represents non-English literature: French (92 works), Chinese (13), Japanese (29). bibCNRS adds 233 non-English works.
- Chinese-language literature (CNKI) remains largely uncovered — bibCNRS adds 76 works (mostly Taiwanese via HyRead) but mainland CNKI (thousands of works for 绿色金融) has no open API.
- German-language literature is adequately covered by OpenAlex (~90 works for "Klimafinanzierung")
- bibCNRS exports include 63 NEWS items (press clippings) which inflate the count but have limited academic value
