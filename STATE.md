# State

Last updated: 2026-03-23

## Status: SUBMITTED

Submitted to Oeconomia (Varia) on 2026-03-18. Under double-blind review.
- Zenodo: https://doi.org/10.5281/zenodo.19097045
- HAL: hal-05558422v1
- Git tag: v1.0-submission

## Manuscript

- ~8,860 words, 61 bib entries — submitted as anonymized PDF
- 2 figures (bars, composition) + 2 tables (traditions, venues), no supplement
- Structural break language purged; computational claims now descriptive
- `\newpage` before each section and each table; fig-composition in §2.5
- No Introduction heading (Oeconomia style); EU Structural Funds compressed
- Per-document vars files (`content/*-vars.yml`) via `{{< meta >}}` shortcode

## Corpus

- Torch installs CPU or CUDA via `--extra cpu` / `--extra cu130` (uv extras with conflicts)
- DVC pipeline split into per-source stages (catalog_istex, catalog_openalex, etc.)
- Semantic Scholar enabled (33,897 works harvested, 1000-per-query API cap)
- OpenAlex Premium API key configured ($2/day budget)
- `--from-date` incremental filtering added (sidecar auto-detection)
- `python-dotenv` loads `.env` secrets automatically
- All HTTP callers use unified retry_get (5 retries, backoff+jitter, 429+5xx)
- Budget guard: catalog_openalex stops gracefully when daily budget exhausted
- Syllabi fetch stage parallelized: 100 workers, per-host rate limiting (1 req/s)
- `in_v1` provenance column in refined_works.csv (29,696 / 52,682 rows match v1.0-submission)

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 135mm, starts 1992
- Fig 2 (composition): relocated to §2.5 (one figure per section)
- Table 1 (traditions): inline pipe table, Pandoc float (no raw LaTeX)
- Table 2 (venues): 15 journals by pole lean, via `{{< include tables/tab_venues.md >}}`
- Table (poles): efficiency vs accountability terms — in companion paper

## Build system

- `make manuscript` is Phase 3 pure: only `quarto render` (no Python, no stats, no API)
- Project-wide include deps on render targets (Quarto resolves includes across all `_quarto.yml` files); surgical figure deps per document
- No data files, no API calls, no Phase 1 caches required during render
- Manuscript deps: .qmd + manuscript-vars.yml + 2 figures + all project includes + bibliography
- All Phase 2 generated tables (including .md) in gitignored `content/tables/`; manuscripts include them via `{{< include >}}`

## Blockers

None.

## Active PRs

None.

## Recent merges (2026-03-23)

- #290/#283: Add `in_v1` provenance column — marks v1.0-submission rows in refined_works.csv
- #268/#265: Parallelize syllabi fetch stage (100 workers, per-host 1 req/s rate limiting, ~10-15x speedup)
- #259: Teaching scraper: improved PDF parsing (table extraction, 50KB limit, chunk overlap), removed manual catalog — scraper is now sole source
- #260: ISTEX rebuild
- #273: Corpus source table generated, not hardcoded (fixes stale ISTEX=4)
- #241: housekeeping STATE refresh
- #245: overnight log 2026-03-20
- #242: overnight exploration runbook
- #243: data paper journal survey + Scientific Data alignment
- #244: ESHET-HES slides first draft + plan
- #231–#235: refactoring wave (detect_communities, archive_traditions logging, collect_syllabi split, classify_type, long functions)

## Next actions

- Prepare ESHET-HES conference slides (Nice, May 26–29) — first draft merged (#244), needs author review
- Data paper: choose journal target (Scientific Data vs DSJ) — survey merged (#243)
- Continue reading plan (Tier 1 books)

## Open tickets

- ~~#283: Add in_v1 provenance column~~ (merged #290)
- #213: Add export_citation_coverage.py to archive-analysis recipe
- #236: Harness extraction — split workflow harness into its own repo
- #237: Harness — offline file-based ticket system (gh-optional)
- #238: Harness — intellectual audit against SE canon
- #239: Harness — type assertion and script hygiene guidelines
- #240: Harness — sweep disk for reusable guidelines from past projects
