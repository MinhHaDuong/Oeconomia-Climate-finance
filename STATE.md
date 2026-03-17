# State

Last updated: 2026-03-17

## Manuscript

- ~9,400 words (target ~9,000), 61 bib entries
- 2 figures (bars, composition) + 2 tables (traditions, venues), no supplement
- Structural break language purged; computational claims now descriptive
- `\newpage` before each section; fig-composition moved to §2.5

## Corpus

- Torch installs CPU or CUDA via `--extra cpu` / `--extra cu130` (uv extras with conflicts)
- Corpus regen in progress on padme (nohup)
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
- Table 2 (venues): 15 journals by pole lean, via `{{< include tab_venues.md >}}`
- Table (poles): efficiency vs accountability terms — in companion paper

## Build system

- `make manuscript` is now Phase 3 pure: only `compute_stats.py` + `quarto render`
- Per-document include sets (no wildcard); surgical figure/table deps
- No API calls, no Phase 1 caches required during render

## Blockers

- Corpus regen must complete before figures/tables/variables can update

## Active PRs

None.

## Open tickets

- #26: Human proofread of full manuscript
