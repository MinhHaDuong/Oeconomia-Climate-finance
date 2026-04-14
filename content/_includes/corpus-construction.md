## Discovery Sources

### Sources

The corpus assembles academic and grey literature from {{< meta corpus_sources >}} sources. Three are fully automated (reproducible from the repository and an internet connection), one is hybrid-automated, and two require manual export.

| Source | Script | Automation | Coverage |
|---|---|---|---|
| OpenAlex | `catalog_openalex.py` | Automated (free API) | Primary academic source: tiered keyword search (4 tiers, ~50 queries) |
| ISTEX | `catalog_istex.py --api` | Automated (public API) | French national archive: `"climate finance" OR "finance climat" OR "finance climatique"` |
| Grey literature | `catalog_grey.py` | Hybrid (YAML seed + World Bank API) | OECD, UNFCCC, World Bank, CPI reports |
| Teaching canon | `build_teaching_canon.py` | Automated (scraping + LLM extraction) | Syllabus readings from 51 institutions |
| bibCNRS | `catalog_bibcnrs.py` | **Hand-harvested** (CNRS Janus auth) | Non-English literature (FR, ZH, JA) via WoS/EconLit/FRANCIS |
| SciSpace | `catalog_scispace.py` | **Hand-harvested** (commercial tool) | AI-curated thematic corpus (RIS + CSV exports) |

The two hand-harvested sources cannot currently be automated: bibCNRS requires CNRS institutional credentials with no public API, and SciSpace is a commercial AI research tool requiring manual export. Together they contribute ~900 works before deduplication (~3% of the unified corpus), primarily filling gaps in non-English coverage and AI-curated seed papers. Their inclusion is justified by multi-source overlap validation: over 500 works appear in both a hand-harvested and an automated source, confirming retrieval consistency.

### Search strategy: tiered keyword taxonomy

The search strategy uses a four-tier query taxonomy reflecting the evolving vocabulary of climate finance scholarship. The taxonomy is defined in `config/openalex_queries.yaml` and was informed by keyword mining of {{< meta corpus_core >}} core papers (cited_by_count >= {{< meta corpus_core_threshold >}}).

**Tier 1 — Core terms** (no post-filter): Unambiguous climate finance terminology in eight languages. English (`"climate finance"`, `"carbon finance"`), French (`"finance climat"`, `"finance climatique"`), German (`"Klimafinanzierung"`), Spanish (`"financiamiento climático"`), Portuguese (`"financiamento climático"`), Arabic, Chinese (`"气候金融"`, `"气候融资"`), Japanese (`"気候金融"`, `"気候ファイナンス"`). Also includes institution names: `"green climate fund"`, `"adaptation fund"`.

**Tier 2 — Institutional and diplomatic vocabulary** (no post-filter): Specific enough to produce relevant results without concept-group filtering. Covers the Kyoto era (`"clean development mechanism"`, `"GEF climate"`), UNFCCC architecture (`"UNFCCC financial mechanism"`, `"article 9 Paris agreement"`, `"new collective quantified goal"`), post-Paris instruments (`"loss and damage fund"`, `"just transition finance"`), markets (`"climate bonds"`, `"green bonds climate"`, `"REDD+ finance"`), MDB reform, and financial flows (`"adaptation financing"`, `"mitigation finance"`, `"climate risk finance"`, `"stranded assets"`).

**Tier 3 — Broader scholarly terms** (2-of-4 concept-group filter): Climate-adjacent terms (`"carbon market development"`, `"green investment climate"`, `"climate investment fund"`) that require abstract text to mention at least 2 of 4 concept groups (climate, finance, development, environment) for inclusion.

**Tier 4 — Disciplinary context** (3-of-4 concept-group filter): Very broad terms (`"environmental economics climate"`, `"ecological economics climate"`) requiring 3-of-4 concept groups for inclusion.

### Temporal scope

All API queries are bounded to publication years 1990–2024, configured in `config/corpus_collect.yaml`. This ensures reproducibility: runs at different dates return the same year window. The pool is append-only — changing year bounds limits what new queries add but does not delete existing records.

### Data architecture

Raw API responses are stored in an append-only pool (`pool/openalex/`, `pool/istex/`) as gzipped JSONL files — one file per query term. This preserves the complete API response for future re-extraction without re-downloading. Extracted records are derived reproducibly into `*_works.csv` catalog files. Citation links from OpenAlex's `referenced_works` field are extracted directly during the catalog build, reducing dependence on Crossref for citation enrichment.

### Why not Crossref for discovery?

OpenAlex indexes 100% of Crossref's DOI registry and adds abstracts, concepts, topics, and affiliations that Crossref lacks. Using Crossref as a discovery source would be fully redundant with OpenAlex. Crossref remains used exclusively for enriching citation reference lists (via `enrich_citations_batch.py` + `enrich_citations_openalex.py`) where OpenAlex's `referenced_works` field is incomplete.

### Other sources

- **ISTEX:** The ISTEX search API (`api.istex.fr`) is queried for `"climate finance" OR "finance climat" OR "finance climatique"`. Raw responses are stored in the pool (`pool/istex/`) following the same append-only architecture as OpenAlex. ISTEX adds full-text metadata from Springer, Elsevier, and Wiley archives accessible through the French national license.
- **bibCNRS** (hand-harvested): Title-field searches in French (`"finance climat"`), Chinese (`"气候金融"`), and Japanese (`"気候金融"`) on the bibCNRS portal (`bib.cnrs.fr`), which aggregates WoS, EconLit, and FRANCIS. Requires CNRS Janus institutional credentials; no public API exists. RIS exports are saved to `data/exports/` and parsed by the script. Harvested February 2026; 242 works.
- **SciSpace** (hand-harvested): An AI-curated corpus produced by SciSpace's systematic review tool, exported as RIS and CSV files. The tool's proprietary discovery algorithm complements keyword-based search. Harvested January 2026; 663 works.
- **Grey literature:** A curated YAML seed list (`config/grey_sources.yaml`, 16 key policy documents from OECD, UNFCCC, CPI) plus automated search of the World Bank Open Knowledge Repository API using three queries: `"climate finance"`, `"climate change policy" AND finance`, and `"financial mechanisms" AND climate`. Each query is capped at 500 results; results are deduplicated by UUID across queries. Fully reproducible.
- **Teaching canon:** An automated web scraper (`catalog_syllabi.py`) harvests university course syllabi via DuckDuckGo search and curated seed URLs, downloads HTML/PDF content, classifies pages with an LLM, and extracts bibliographic references. PDF parsing uses pdfplumber to capture reading lists in any format. The normalize stage deduplicates references across syllabi, cleans DOIs (stripping URL prefixes), and enriches title-only references via OpenAlex DOI resolution (shared cache with the main corpus enrichment). Title-only references undergo fuzzy deduplication (rapidfuzz token sort ratio at 75%) so that edition variants and paraphrases aggregate their course counts. Readings then pass a two-tier convergence filter: detailed syllabi (≥20 DOI readings, e.g. doctoral seminars) pass at ≥1 course; standard readings require DOI + ≥2 courses or title-only + ≥3 courses. The result is converted to `teaching_works.csv` by `build_teaching_canon.py`, and the merge pipeline sets the `from_teaching` provenance flag.

### Merge and deduplication

The merge script (`scripts/catalog_merge.py`) first normalizes all text fields (titles, abstracts, author names, journals, keywords) to fix encoding artifacts inherited from upstream aggregators: HTML entities are decoded, mojibake from double-encoded UTF-8 is repaired, and invisible characters (zero-width spaces, soft hyphens, BOM markers) are stripped. A small number of author names (29 records, 0.09% of the corpus) contain Unicode replacement characters (U+FFFD) due to encoding errors in upstream metadata deposits at the publisher level; these are present in both the OpenAlex and Crossref APIs and cannot be repaired programmatically. The merge script then applies two deduplication passes:

1. **DOI-based deduplication:** DOIs are normalized (lowercased, URL prefix stripped). Records sharing the same DOI are merged using a source priority order: openalex > scopus > istex > bibcnrs > scispace > grey > teaching. The maximum `cited_by_count` across duplicates is retained; other fields use the best non-empty value following source priority.
2. **Title+year deduplication:** Records without DOIs are grouped by normalized title (lowercased, punctuation stripped) and year. Groups are merged using the same priority logic.

Boolean `from_*` columns (one per source) track which databases contributed to each record, and `source_count` is their sum. The `source` column retains the primary source (highest in the priority order). The output is `unified_works.csv`.

### Pipeline summary

The corpus building pipeline is managed by DVC (Data Version Control; see @fig-dag). The five discovery stages run independently; their outputs are merged into a single catalog, then enriched, refined, and aligned in a linear chain. Enrichment runs on the full `unified_works.csv` so that all metadata is available when the flagging rules are evaluated. The extend step computes six quality flags for every work without removing any rows; the filter step applies the retention policy and writes `refined_works.csv` together with `corpus_audit.csv`. The align step produces the Phase 2 canonical inputs (`refined_embeddings.npz`, `refined_citations.csv`) from full enrichment caches.

