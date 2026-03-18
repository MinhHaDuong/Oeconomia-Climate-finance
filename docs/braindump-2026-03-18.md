# Braindump 2026-03-18

Parked ideas for post-submission.

## Repro packages (phase 4)

- Based on manifest.txt auto-generated from the Makefile (+AI sandbox validation)
- Each phase gets its own repro package with its own repro note
- Phase 1: corpus → data paper IS the repro note
- Phase 2: analysis → scripts + frozen inputs + outputs
- Phase 3: editorial → qmd + figures (different from phase 2)
- Tech rep = mechanical compilation of all repro notes (stays current by construction)

## Makefile modularization

- `makefile.d/` with per-phase includes
- Top-level Makefile defines contracts (phony targets), each phase gets its own `.mk`
- Phases 1 and 3 are thin shims (dvc repro, quarto render); phase 2 has the real dep graph

## qmd vs tex

- Not convinced qmd > tex for Oeconomia
- Escape hatch: `quarto render --to latex` if journal wants .tex source
- Switching cost probably not worth it now since qmd already works

## Skill-based agent coordination

- Replace fixed "agent perspective" tables with composable skill pool
- Skills: atomic markdown files (one sentence scope each)
- Experts: named skill bundles + perspective (yaml)
- Coordinators: runbooks assemble purpose-built teams per event
- Directory structure: `skills/`, `experts/`, `runbooks/`
- Hybrid model: experts are sensible defaults, coordinator can add/drop skills per task
- Academic metaphor: skill=expertise, expert=reviewer, coordinator=editor
- Applies broadly: review, doing, planning, any multi-agent step
- Could become a reusable framework beyond this paper

## Local issue tracking (replace GitHub Issues)

- Track tickets and PR discussions in-repo via git, not online GitHub
- One approach: replace `gh` with a custom script (like GSD uses tasks)
- Dev is just user+agents, no external collaborators right now
- Pros: works offline, possibly faster, full history in git
- Cons: reinventing the wheel, harder to onboard helpers later

## Conversation logging & replay

- Memorize all conversations and tool calls
- Can verify which `gh` functions are actually used (audit before replacing)
- Night loop: replay conversations on padme to benchmark other agents
  - ollama or openrouter (e.g., minimax 4.7)
  - Tests whether other agents handle the harness as well as Claude
  - Can also use replays to refine the harness itself (as minimax team did)

## Polars (Rust pandas replacement)

- Evaluate replacing pandas with Polars in Phase 2 scripts
- Already had `iterrows()` performance issues on 20K+ DataFrames
- Polars: lazy evaluation, Rust-backed, 5–20x faster on large frames
- By Ritchie Vink / pola-rs (not Astral — different Rust-for-Python project)
- Risk: matplotlib integration less mature, learning curve
- Good candidate for a post-submission rewrite if data paper needs heavier computation

## Open questions (to resolve post-submission)

- Phase 2 repro package: pointer to phase 1 (DOI) or bundled snapshot?
- Data paper: standalone submission (Scientific Data/JOSS) or HAL working paper?
- manifest.txt: walk Make DAG, DVC DAG, or both?
- AI sandbox validation: CI job in container?
- Skill granularity: one-sentence test
- Coordination: explicit (runbook prescribes) vs inferred (coordinator reads diff)
