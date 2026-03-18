# State

Last updated: 2026-03-18

## Manuscript

- ~8,860 words (target ~9,000), 61 bib entries
- 2 figures (bars, composition) + 2 tables (traditions, venues), no supplement
- Structural break language purged; computational claims now descriptive
- `\newpage` before each section and each table; fig-composition in §2.5
- No Introduction heading (Oeconomia style); EU Structural Funds compressed
- Per-document vars files (`content/*-vars.yml`) via `{{< meta >}}` shortcode

## Corpus

- Torch installs CPU or CUDA via `--extra cpu` / `--extra cu130` (uv extras with conflicts)
- DVC pipeline split into per-source stages (catalog_istex, catalog_openalex, etc.)
- Semantic Scholar skipped for pre-submission (rate-limited, minor source)
- OpenAlex Premium API key configured ($2/day budget)
- `--from-date` incremental filtering added (sidecar auto-detection)
- `python-dotenv` loads `.env` secrets automatically
- All HTTP callers use unified retry_get (5 retries, backoff+jitter, 429+5xx)
- Budget guard: catalog_openalex stops gracefully when daily budget exhausted

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992
- Fig 2 (composition): relocated to §2.5 (one figure per section)
- Table 1 (traditions): inline pipe table, Pandoc float (no raw LaTeX)
- Table 2 (venues): 15 journals by pole lean, via `{{< include tables/tab_venues.md >}}`
- Table (poles): efficiency vs accountability terms — in companion paper

## Build system

- `make manuscript` is Phase 3 pure: only `quarto render` (no Python, no stats, no API)
- Per-document include sets (no wildcard); surgical figure/table deps
- No data files, no API calls, no Phase 1 caches required during render
- Manuscript deps: .qmd + manuscript-vars.yml + 2 figures + content/tables/tab_venues.md + bibliography
- All Phase 2 generated tables (including .md) in gitignored `content/tables/`; `content/_includes/` is hand-written only

## Blockers

None.

## Active PRs

None.

## Open tickets

- #26: Human proofread of full manuscript
- #213: Add export_citation_coverage.py to archive-analysis recipe
