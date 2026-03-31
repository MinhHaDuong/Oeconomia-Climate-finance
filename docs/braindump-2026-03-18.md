# Braindump 2026-03-18

Parked ideas for post-submission.

> **Status review 2026-03-28**: Both papers submitted (Oeconomia 03-18, RDJ4HSS 03-26). Annotations below.

## Repro packages (phase 4)

> **DONE** — Phase 4 documented (#502), archive helpers in `release/` (#495, #493), build scripts extracted (#500). Three archive builders in `release/scripts/` (manuscript, datapaper, analysis). Makefile targets `archive-*`. manifest.txt auto-generation and per-phase repro notes not yet built.

- Based on manifest.txt auto-generated from the Makefile (+AI sandbox validation)
- Each phase gets its own repro package with its own repro note
- Phase 1: corpus → data paper IS the repro note
- Phase 2: analysis → scripts + frozen inputs + outputs
- Phase 3: editorial → qmd + figures (different from phase 2)
- Tech rep = mechanical compilation of all repro notes (stays current by construction)

## qmd vs tex

> **MOOT** — Both submissions used qmd successfully. Revisit only if a journal requests .tex source.

- Not convinced qmd > tex for Oeconomia
- Escape hatch: `quarto render --to latex` if journal wants .tex source
- Switching cost probably not worth it now since qmd already works

## Conversation logging & replay

> **PARTIAL** — Agentic harness telemetry module landed (#489). `get_logger()` in `scripts/utils.py`, no bare `print()` enforced by `test_script_hygiene.py`. Full conversation replay and ollama benchmarking not started.

- Memorize all conversations and tool calls
- Can verify which `gh` functions are actually used (audit before replacing)
- Night loop: replay conversations on padme to benchmark other agents
  - ollama or openrouter (e.g., minimax 4.7)
  - Tests whether other agents handle the harness as well as Claude
  - Can also use replays to refine the harness itself (as minimax team did)

## Polars (Rust pandas replacement)

> **DONE** — Benchmarked in `content/_includes/reproducibility.md`. Polars 3–33× faster on I/O, 2–3× on compute, but migrating 108 files not worth it. Retained pandas. Also evaluated Parquet/Feather storage formats.

- Evaluate replacing pandas with Polars in Phase 2 scripts
- Already had `iterrows()` performance issues on 20K+ DataFrames
- Polars: lazy evaluation, Rust-backed, 5–20x faster on large frames
- By Ritchie Vink / pola-rs (not Astral — different Rust-for-Python project)
- Risk: matplotlib integration less mature, learning curve
- Good candidate for a post-submission rewrite if data paper needs heavier computation

## Open questions (to resolve post-submission)

- Phase 2 repro package: pointer to phase 1 (DOI) or bundled snapshot?
- ~~Data paper: standalone submission (Scientific Data/JOSS) or HAL working paper?~~ **RESOLVED** — submitted to RDJ4HSS (diamond OA), under review since 2026-03-26.
- manifest.txt: walk Make DAG, DVC DAG, or both?
- AI sandbox validation: CI job in container?
