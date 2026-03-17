# State

Last updated: 2026-03-17

## Manuscript

- ~9,600 words (target ~9,000), 61 bib entries
- 2 figures (emergence, composition) + 3 tables (traditions, poles, venues) + 1 supplement figure (seed axis)
- Variable dependencies reduced to 1 (`corpus_total_approx`)

## Corpus

- Corpus regen in progress on padme (nohup)
- DVC pipeline split into per-source stages (catalog_istex, catalog_openalex, etc.)
- Semantic Scholar skipped for pre-submission (rate-limited, minor source)
- OpenAlex Premium API key configured ($2/day budget)
- `--from-date` incremental filtering added (sidecar auto-detection)
- `python-dotenv` loads `.env` secrets automatically

## Figures & tables

- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992
- Fig 2 (composition): relocated to §3.4 (thematic decomposition argument)
- Fig S1 (traditions): co-citation network, color, Electronic Supplement
- Fig S2 (seed axis): efficiency–accountability scatter, Electronic Supplement
- Table 1 (traditions): caption updated; §1.5 cites co-citation evidence (Q=0.68)
- Table 2 (venues): 17 journals by pole lean, replaces @fig-seed in body
- Table (poles): efficiency vs accountability terms — in companion paper

## Blockers

- Corpus regen must complete before figures/tables/variables can update

## Active PRs

None.

## Open tickets

- #171: Bug — OpenAlex requests crash on transient 429 despite valid API key
- #26: Human proofread of full manuscript
