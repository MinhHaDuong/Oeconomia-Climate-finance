## 1. Corpus Construction

### Sources

The corpus assembles academic and grey literature from eight sources:

| Source | Script | Coverage |
|---|---|---|
| OpenAlex | `catalog_openalex.py` | Primary academic source: tiered keyword search (4 tiers, ~50 queries) |
| Semantic Scholar | `catalog_semanticscholar.py` | Complementary discovery: arXiv, theses, working papers |
| ISTEX | `catalog_istex.py` | French national archive (full-text JSON) |
| bibCNRS | `catalog_bibcnrs.py` | Non-English literature (FR, ZH, JA, DE, ES, PT) |
| SciSpace | `catalog_scispsace.py` | AI-curated thematic corpus |
| Grey literature | `catalog_grey.py` | OECD, UNFCCC, World Bank, CPI reports |
| Teaching canon | manual | Papers appearing in 2+ syllabi |

### Search strategy: tiered keyword taxonomy

The search strategy uses a four-tier query taxonomy reflecting the evolving vocabulary of climate finance scholarship. The taxonomy is defined in `data/openalex_queries.yaml` and was informed by keyword mining of 1,406 core papers (cited_by_count >= 50).

**Tier 1 — Core terms** (no post-filter): Unambiguous climate finance terminology in eight languages. English (`"climate finance"`, `"carbon finance"`), French (`"finance climat"`, `"finance climatique"`), German (`"Klimafinanzierung"`), Spanish, Portuguese, Arabic, Chinese, Japanese. Also includes institution names: `"green climate fund"`, `"adaptation fund"`.

**Tier 2 — Institutional and diplomatic vocabulary** (no post-filter): Specific enough to produce relevant results without concept-group filtering. Covers the Kyoto era (`"clean development mechanism"`, `"GEF climate"`), UNFCCC architecture (`"UNFCCC financial mechanism"`, `"article 9 Paris agreement"`, `"new collective quantified goal"`), post-Paris instruments (`"loss and damage fund"`, `"just transition finance"`), markets (`"climate bonds"`, `"green bonds climate"`, `"REDD+ finance"`), MDB reform, and financial flows (`"adaptation financing"`, `"mitigation finance"`, `"climate risk finance"`, `"stranded assets"`).

**Tier 3 — Broader scholarly terms** (2-of-4 concept-group filter): Climate-adjacent terms (`"carbon market development"`, `"green investment climate"`, `"climate investment fund"`) that require abstract text to mention at least 2 of 4 concept groups (climate, finance, development, environment) for inclusion.

**Tier 4 — Disciplinary context** (3-of-4 concept-group filter): Very broad terms (`"environmental economics climate"`, `"ecological economics climate"`) requiring 3-of-4 concept groups for inclusion.

### Data architecture

Raw API responses are stored in an append-only pool (`pool/openalex/`, `pool/semanticscholar/`) as gzipped JSONL files — one file per query term. This preserves the complete API response for future re-extraction without re-downloading. Extracted records are derived reproducibly into `*_works.csv` catalog files. Citation links from OpenAlex's `referenced_works` field are extracted directly during the catalog build, reducing dependence on Crossref for citation enrichment.

### Why not Crossref for discovery?

OpenAlex indexes 100% of Crossref's DOI registry and adds abstracts, concepts, topics, and affiliations that Crossref lacks. Using Crossref as a discovery source would be fully redundant with OpenAlex. Crossref remains used exclusively for enriching citation reference lists (via `enrich_citations.py`) where OpenAlex's `referenced_works` field is incomplete.

### Other sources

- **ISTEX:** Full-text query `"climate finance" OR "finance climat" OR "finance climatique"` on the French national archive.
- **bibCNRS:** Title-field searches in French, Chinese, Japanese, German, Spanish, Portuguese. Manual RIS export from `bib.cnrs.fr`.
- **Grey literature:** A curated YAML seed list (16 key policy documents) plus the World Bank Open Knowledge Repository API.
- **Semantic Scholar:** Same tiered queries. Adds coverage of arXiv preprints, dissertations, and working papers that OpenAlex may miss. Free API with offset-based pagination (capped at ~10K per query).

### Merge and deduplication

The merge script (`scripts/catalog_merge.py`) applies two deduplication passes:

1. **DOI-based deduplication:** DOIs are normalized (lowercased, URL prefix stripped). Records sharing the same DOI are merged using a source priority order: openalex > semanticscholar > scopus > istex > jstor > bibcnrs > scispsace > grey > teaching. The maximum `cited_by_count` across duplicates is retained; other fields use the best non-empty value following source priority.
2. **Title+year deduplication:** Records without DOIs are grouped by normalized title (lowercased, punctuation stripped) and year. Groups are merged using the same priority logic.

A `source_count` field tracks how many sources contributed to each record. The output is `unified_works.csv`.

### Relevance filtering

Corpus refinement (`scripts/corpus_refine.py`) applies six flags:

1. Missing metadata (title, author, year)
2. No abstract with irrelevant title
3. Title blacklist (blockchain, cryptocurrency, etc. — unless title also has climate/finance safe words)
4. Citation isolation: pre-2019 papers with DOI but no citations in or out of corpus
5. Semantic outlier: >2σ from embedding centroid (cosine distance)
6. LLM relevance: papers with weak concept-group coverage scored by Gemini Flash; irrelevant papers flagged

Papers are protected from removal if they have high citations (>=50), appear in multiple sources, are cited within the corpus, or belong to the teaching canon. A random-sample LLM audit verifies Type I/II error rates.
