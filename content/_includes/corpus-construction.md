## 1. Corpus Construction

### Sources

The corpus assembles academic and grey literature from {{< var corpus_sources >}} sources. Four are fully automated or hybrid-automated (reproducible from the repository and an internet connection); two require manual export and are documented below with justification.

| Source | Script | Automation | Coverage |
|---|---|---|---|
| OpenAlex | `catalog_openalex.py` | Automated (free API) | Primary academic source: tiered keyword search (4 tiers, ~50 queries) |
| ISTEX | `catalog_istex.py --api` | Automated (public API) | French national archive: `"climate finance" OR "finance climat" OR "finance climatique"` |
| Grey literature | `catalog_grey.py` | Hybrid (YAML seed + World Bank API) | OECD, UNFCCC, World Bank, CPI reports |
| Teaching canon | `build_teaching_canon.py` | Automated (YAML extraction) | Syllabus readings from 15 institutions |
| bibCNRS | `catalog_bibcnrs.py` | **Hand-harvested** (CNRS Janus auth) | Non-English literature (FR, ZH, JA) via WoS/EconLit/FRANCIS |
| SciSpace | `catalog_scispsace.py` | **Hand-harvested** (commercial tool) | AI-curated thematic corpus (RIS + CSV exports) |

The two hand-harvested sources cannot currently be automated: bibCNRS requires CNRS institutional credentials with no public API, and SciSpace is a commercial AI research tool requiring manual export. Together they contribute ~900 works before deduplication (~3% of the unified corpus), primarily filling gaps in non-English coverage and AI-curated seed papers. Their inclusion is justified by multi-source overlap validation: over 500 works appear in both a hand-harvested and an automated source, confirming retrieval consistency.

### Search strategy: tiered keyword taxonomy

The search strategy uses a four-tier query taxonomy reflecting the evolving vocabulary of climate finance scholarship. The taxonomy is defined in `config/openalex_queries.yaml` and was informed by keyword mining of 1,406 core papers (cited_by_count >= 50).

**Tier 1 — Core terms** (no post-filter): Unambiguous climate finance terminology in eight languages. English (`"climate finance"`, `"carbon finance"`), French (`"finance climat"`, `"finance climatique"`), German (`"Klimafinanzierung"`), Spanish, Portuguese, Arabic, Chinese, Japanese. Also includes institution names: `"green climate fund"`, `"adaptation fund"`.

**Tier 2 — Institutional and diplomatic vocabulary** (no post-filter): Specific enough to produce relevant results without concept-group filtering. Covers the Kyoto era (`"clean development mechanism"`, `"GEF climate"`), UNFCCC architecture (`"UNFCCC financial mechanism"`, `"article 9 Paris agreement"`, `"new collective quantified goal"`), post-Paris instruments (`"loss and damage fund"`, `"just transition finance"`), markets (`"climate bonds"`, `"green bonds climate"`, `"REDD+ finance"`), MDB reform, and financial flows (`"adaptation financing"`, `"mitigation finance"`, `"climate risk finance"`, `"stranded assets"`).

**Tier 3 — Broader scholarly terms** (2-of-4 concept-group filter): Climate-adjacent terms (`"carbon market development"`, `"green investment climate"`, `"climate investment fund"`) that require abstract text to mention at least 2 of 4 concept groups (climate, finance, development, environment) for inclusion.

**Tier 4 — Disciplinary context** (3-of-4 concept-group filter): Very broad terms (`"environmental economics climate"`, `"ecological economics climate"`) requiring 3-of-4 concept groups for inclusion.

### Data architecture

Raw API responses are stored in an append-only pool (`pool/openalex/`, `pool/semanticscholar/`, `pool/istex/`) as gzipped JSONL files — one file per query term. This preserves the complete API response for future re-extraction without re-downloading. Extracted records are derived reproducibly into `*_works.csv` catalog files. Citation links from OpenAlex's `referenced_works` field are extracted directly during the catalog build, reducing dependence on Crossref for citation enrichment.

### Why not Crossref for discovery?

OpenAlex indexes 100% of Crossref's DOI registry and adds abstracts, concepts, topics, and affiliations that Crossref lacks. Using Crossref as a discovery source would be fully redundant with OpenAlex. Crossref remains used exclusively for enriching citation reference lists (via `enrich_citations_batch.py` + `enrich_citations_openalex.py`) where OpenAlex's `referenced_works` field is incomplete.

### Other sources

- **ISTEX:** The ISTEX search API (`api.istex.fr`) is queried for `"climate finance" OR "finance climat" OR "finance climatique"`. Raw responses are stored in the pool (`pool/istex/`) following the same append-only architecture as OpenAlex. ISTEX adds full-text metadata from Springer, Elsevier, and Wiley archives accessible through the French national license.
- **bibCNRS** (hand-harvested): Title-field searches in French (`"finance climat"`), Chinese (`"气候金融"`), and Japanese (`"気候金融"`) on the bibCNRS portal (`bib.cnrs.fr`), which aggregates WoS, EconLit, and FRANCIS. Requires CNRS Janus institutional credentials; no public API exists. RIS exports are saved to `data/exports/` and parsed by the script. Harvested February 2026; 242 works.
- **SciSpace** (hand-harvested): An AI-curated corpus produced by SciSpace's systematic review tool, exported as RIS and CSV files. The tool's proprietary discovery algorithm complements keyword-based search. Harvested January 2026; 663 works.
- **Grey literature:** A curated YAML seed list (`config/grey_sources.yaml`, 16 key policy documents from OECD, UNFCCC, CPI) plus automated search of the World Bank Open Knowledge Repository API (capped at 200 results). Fully reproducible.
- **Teaching canon:** Syllabus readings scraped from ~130 courses are collected in `data/syllabi/reading_lists.csv` by `collect_syllabi.py`, converted to `data/teaching_sources.yaml` by `build_teaching_yaml.py`, and extracted into `teaching_works.csv` by `build_teaching_canon.py`. The merge pipeline deduplicates these against other sources and sets the `from_teaching` provenance flag.

### Merge and deduplication

The merge script (`scripts/catalog_merge.py`) applies two deduplication passes:

1. **DOI-based deduplication:** DOIs are normalized (lowercased, URL prefix stripped). Records sharing the same DOI are merged using a source priority order: openalex > semanticscholar > scopus > istex > bibcnrs > scispsace > grey > teaching. The maximum `cited_by_count` across duplicates is retained; other fields use the best non-empty value following source priority.
2. **Title+year deduplication:** Records without DOIs are grouped by normalized title (lowercased, punctuation stripped) and year. Groups are merged using the same priority logic.

Boolean `from_*` columns (one per source) track which databases contributed to each record, and `source_count` is their sum. The `source` column retains the primary source (highest in the priority order). The output is `unified_works.csv`.

### Pipeline overview

The full corpus pipeline runs in five steps (Makefile targets: `corpus-discover`,
`corpus-enrich`, `corpus-extend`, `corpus-filter`, `corpus-align`):

```
  7 sources ──→ merge ──→ unified_works.csv   [corpus-discover]
                               │
                               ▼
                        enrich DOIs / abstracts / citations
                               │
                               ▼
                        enriched_works.csv      [corpus-enrich]
                               │
                               ▼
                        flag all works (flags 1-6, no rows removed)
                               │
                               ▼
                        extended_works.csv      [corpus-extend]
                               │
                               ▼
                        apply policy → audit → refined_works.csv  [corpus-filter]
                               │
                               ▼
                        align caches to filtered rows:
                        refined_embeddings.npz + refined_citations.csv  [corpus-align]
```

Enrichment (DOIs via OpenAlex, abstracts from OA/S2/ISTEX, citations from
Crossref and OpenAlex) runs on the full `unified_works.csv` so that all
metadata is available when the flagging rules are evaluated. The extend step
computes six quality flags for every work without removing any rows; the
filter step then applies the retention policy and writes the final
`refined_works.csv` together with `corpus_audit.csv`. The align step then
produces the Phase 2 canonical inputs (`refined_embeddings.npz`,
`refined_citations.csv`) from full enrichment caches. See §2 (Corpus
Enrichment) and §3 (Corpus Refinement) for details.

