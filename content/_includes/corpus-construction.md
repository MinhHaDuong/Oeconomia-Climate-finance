## 1. Corpus Construction

### Sources

The corpus assembles academic and grey literature from seven sources:

| Source | Script | Records | Coverage |
|---|---|---|---|
| OpenAlex | `catalog_openalex.py` | ~11,313 | Broad English-language academic literature |
| OpenAlex (historical) | `catalog_openalex_historical.py` | variable | Pre-2000 and non-English historical works |
| ISTEX | `catalog_istex.py` | 482 | French national archive (full-text JSON) |
| bibCNRS | `catalog_bibcnrs.py` | 242 | Non-English literature (FR, ZH, JA, DE) |
| SciSpace | `catalog_scispsace.py` | 663 | AI-curated thematic corpus |
| Grey literature | `catalog_grey.py` | 213 | OECD, UNFCCC, World Bank, CPI reports |
| Teaching canon | manual | variable | Papers appearing in 2+ syllabi |

### Search strategy

- **OpenAlex:** Cursor-paginated queries using `filter=default.search:"climate finance"` and `filter=default.search:"finance climat"` (captures French variants). Abstracts reconstructed from OpenAlex inverted index format. Polite-pool access with `mailto` header.
- **ISTEX:** Full-text query `"climate finance" OR "finance climat" OR "finance climatique"` on the national archive.
- **bibCNRS:** Title-field searches in French (`"finance climat" OR "finance climatique"`), Chinese (气候融资 OR 气候金融), Japanese (気候金融 OR グリーンファイナンス OR 気候ファイナンス), and German. Manual RIS export.
- **Grey literature:** A curated YAML seed list (16 key policy documents) plus the World Bank Open Knowledge Repository API (query `"climate finance"`, first 200 results).

### Merge and deduplication

The merge script (`scripts/catalog_merge.py`) applies two deduplication passes:

1. **DOI-based deduplication:** DOIs are normalized (lowercased, URL prefix stripped). Records sharing the same DOI are merged using a source priority order: openalex > openalex_historical > scopus > istex > jstor > bibcnrs > scispsace > grey > teaching. The maximum `cited_by_count` across duplicates is retained; other fields use the best non-empty value following source priority.
2. **Title+year deduplication:** Records without DOIs are grouped by normalized title (lowercased, punctuation stripped) and year. Groups are merged using the same priority logic.

A `source_count` field tracks how many sources contributed to each record. The output is `unified_works.csv`.
