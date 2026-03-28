# Braindump 2026-03-28

Both papers under review. Waiting mode — good time for infrastructure and preparation.

## Regression testing via input/output hashing

Each script maps inputs to outputs. Track (hash_in, hash_out) per script per commit.

**Two use cases:**

1. **PR testing** — run the pipeline, compare output hashes against main. Any change is flagged for review: intended (new feature) or regression (bug)?
2. **Historical analysis** — record hashes at key commits, bisect to find which commit introduced a change in outputs, then verify whether intentional.

Basically a content-addressable audit trail for the pipeline. DVC already tracks file hashes — the gap is connecting them to script identity and making diffs across commits easy to inspect.

## Organize into sub-projects

The repo has grown into four distinct concerns with different lifecycles:

1. **Corpus** — collection, enrichment, DVC pipeline (Phase 1)
2. **Analysis** — embeddings, clustering, break detection (Phase 2)
3. **Oeconomia manuscript** — HPS article, submission branch, revisions
4. **Data paper** — RDJ4HSS, its own submission branch, its own archive
5. **Next paper...**

Currently interleaved in one repo. Each sub-project gets:

- Its own `scripts/`, `config/`, `tests/`, `docs/`, `release/` directories
- Its own `.claude/` (rules, skills, settings scoped to that concern)
- Its own `Makefile` and `README`
- Its own tracked inputs (explicit, versioned)

**Handoff targets** between sub-projects (e.g., `handoff-corpus-to-analysis`):

1. **QA the deliverables** — validate completeness, schema, counts
2. **Copy and adapt** — format conversion at the boundary (e.g., corpus delivers CSV+NPZ, analysis consumes Parquet)

This makes each sub-project self-contained: it doesn't reach into another's internals, it receives a validated snapshot in the format it expects. The handoff script is the contract.

Eases two **PAIN POINTS**:
* Reproductiblity packaging.
* quarto does not pollutes project root and rebuild everything all the time

## Script I/O discipline

**Scripts take input file(s) and output file (singular) as arguments.** No hardcoded filenames.

- No `open("somefile.csv")` or `FILENAME = "somefile.csv"` at the top. The Makefile owns all path naming.
- Missing input or output argument = error. No silent defaults to hardcoded paths. Keep it simple — maybe allow stdin/stdout filtering later, but start strict.
- **Enforcement** (investigated 2026-03-28): Ruff has no rule for this — `S108` only catches hardcoded `/tmp/` paths, and ruff does not support custom plugins (all 900+ rules are built-in Rust). No standard flake8 or pylint plugin exists either. Two viable options:
  1. **Semgrep custom rule** — YAML pattern-matching, quick to write, catches `open("literal")` patterns
  2. **Standalone `ast.walk` script** (~200 lines) — visit `open()` and `Path()` calls, flag string-literal first args; also catch `FILENAME = "..."` assignments. Run as pre-commit check.

**Makefile naming conventions:**

- `fig_NAME.py` → `figures/NAME.pdf` (predictable, greppable)
- Figure scripts accept `--width` and `--dpi` with defaults from a config file (e.g., `_variables.yml` or a `figures.yml`)
- Output format guessed from extension — follow the plotting library conventions (matplotlib `savefig` already does this)
- Generic pattern rule, explicit deps only:
  ```makefile
  # Recipe defined once
  figures/%.pdf: scripts/fig_%.py
  	uv run python $< --output $@ $(filter-out $<,$^)

  # Per-figure: only declare data dependencies (no recipe)
  figures/composition.pdf: data/enriched_works.csv
  figures/bars_v1.pdf: data/enriched_works.csv data/clusters.csv
  ```
  Make merges prerequisites — pattern rule supplies the recipe, extra lines just add deps. `$(filter-out $<,$^)` passes all deps except the script as input args to the script.

- Same principle for tables

**Canonical `main()` for figure/table scripts:**

```python
def main():
    # 1. Parse I/O arguments (shared across all scripts)
    args = parse_io_args()          # --input, --output (required, no defaults)
    validate_io(args)               # inputs exist, output dir writable

    # 2. Parse figure/table arguments (shared across type)
    fig_args = parse_fig_args()     # --width, --dpi (defaults from config)

    # 3. Parse script-specific arguments (if any)
    specific = parse_specific_args()

    # 4. Run — pure computation, no file I/O, no defaults
    result = run(args.input, specific.param1, specific.param2)

    # 5. Save — format guessed from output extension
    save(result, args.output, fig_args.width, fig_args.dpi)
```

Every figure/table script looks the same. Steps 1–2 could be a shared `argparse` parent parser. `run()` is the only function that varies — it takes data in, returns a figure/table object, touches no files.

## Performance monitoring and Polars evaluation

Analysis phase is getting slow. Before switching anything, instrument first:

- **Add timing to scripts** — each `run()` logs wall time and peak memory (e.g., `time.perf_counter` + `tracemalloc`). Makefile captures per-target timing via `time` or a wrapper.
- **Baseline** — record current pandas timings per script on doudou and padme. This is the benchmark to beat.
- **Polars spike** — pick the slowest script, rewrite `run()` with Polars (lazy API), compare wall time and memory. The canonical `main()` pattern above makes this easy: only `run()` changes, I/O stays the same.
- **Decision criteria** — worth switching if 3x+ speedup on the bottleneck script. Not worth it for scripts that already run in seconds.

Note: Polars reads CSV/Parquet natively, so it fits the handoff pattern (corpus delivers CSV, analysis could read directly or via Parquet handoff).

**Static performance analysis** — detect O(n²) patterns before they bite:

- Nested loops over DataFrames (`for row in df.iterrows()` inside another loop)
- `.apply()` calling a function that itself iterates
- Cartesian joins / cross-merges without size guards
- Could be an `ast.walk` check (same tooling as the hardcoded filename lint) or a semgrep rule
- Ruff already has `PERF` rules (`PERF101`–`PERF403`) — check if any cover nested iteration. At minimum `PERF203` (try-except in loop) and `PERF102` (.items() misuse) are already adopted.

## More pipeline guardrails

**Determinism checker** — run each script twice with same inputs, diff outputs. Catches leaking timestamps, unseeded randomness, dict ordering, floating-point non-determinism. Fails the PR if outputs differ.

**Dead asset detection** — walk the Makefile DAG + `import` graph, flag scripts that no target depends on and data files that no script reads. Prevents accumulation of orphan artifacts post-refactor.

**Dependency graph as a figure** — auto-generate a DAG visualization from Makefile + DVC (`make dag` target). `graphviz` from `dvc dag --dot` + Makefile parsing. Useful for the technical report and for onboarding.

**Script complexity budget** — enforce that `run()` is the only function above a cyclomatic complexity threshold per script. Everything else (arg parsing, I/O) should be trivial. Ruff `C901` already exists — the twist is scoping it: low threshold globally, higher allowance only for functions named `run`.

**Memory high-water-mark regression test** — record peak RSS per script in a `.json` baseline. CI compares against it, flags >20% regressions. Catches accidental quadratic memory (e.g., building a full matrix instead of streaming) before the corpus grows and it becomes a crash.

**Schema contracts at handoff boundaries** — each script declares expected input schema (column names, dtypes, non-null constraints) and output schema. Validated before `run()` starts. Catches silent column renames, type drift, and missing fields at the point of failure, not three scripts downstream.

**Smoke pipeline with tiny corpus** — **PAIN POINT**: tests fail when data is not available, which is the case in new worktrees and in isolated environments used by agents. Fix: a 100-row fixture subset that runs the full pipeline end-to-end in <30 seconds. Versioned alongside tests, checked into git (not DVC). `make smoke` vs `make corpus`. Every worktree and every agent sandbox can run the full test suite out of the box, no `dvc pull` required.

**Provenance sidecar files** — each output gets a `.provenance.json` next to it: git commit, script path, input hashes, parameters used, wall time. Any figure or CSV can answer "what exactly produced me?" without digging through git. Trivially generated by the shared `save()` in the canonical `main()`.

**Config drift detection** — diff all config/parameter files (`_variables.yml`, clustering params, embedding model names) across commits. Alert in PR review when a parameter changed but the commit message doesn't mention it. Silent parameter changes are the most common source of unreproducible results.

**Data quality dashboard** — summary stats per corpus version (row counts, null rates, distribution moments, duplicate rates) saved as a JSON snapshot. Diff across versions to detect drift. Catches upstream API changes (OpenAlex schema evolving, S2 returning fewer fields) before they corrupt downstream analysis.

## Review (Claude Opus 4.6, 2026-03-28)

> **Coherence.** A vision runs through this: scripts as pure functions, Makefile as orchestrator, contracts at boundaries, measure before optimizing. The ideas reinforce each other: the canonical `main()` enables provenance sidecars, the sub-project split enables smoke fixtures, the I/O discipline enables the determinism checker. That convergence is a sign the thinking is landing on something real.
>
> **Sub-projects vs. monorepo convenience.** Four Makefiles, four `.claude/` dirs, handoff scripts — that's a lot of ceremony for a solo researcher. The pain points (quarto pollution, repro packaging) are real, but the cure might be worse. Lighter alternative: one repo, one Makefile with namespaced targets (`corpus-collect`, `analysis-embed`, `manuscript-render`), separate `scripts/` dirs but shared config. The handoff contract can be a Make target without full sub-project isolation.
>
> **How much linting infrastructure for ~30 scripts?** The `ast.walk` filename checker, the O(n²) detector, the complexity budget, the dead asset finder — each is ~200 lines, but together they're a custom linting framework. For a project this size, a single "pipeline discipline" pre-commit script might cover 80% of the value. Or just a code review checklist in `.claude/rules/`.
>
> **Smoke pipeline is the highest-leverage idea.** It solves a concrete, recurring problem (tests fail in worktrees/agent sandboxes) and unblocks everything else. Most other guardrails only matter once you can actually run the pipeline in CI. This is a prerequisite, not a peer.
>
> **Provenance sidecars vs. DVC.** DVC already tracks input hashes, parameters, and output hashes in `dvc.lock`. A `.provenance.json` per output duplicates this. The real gap might be making `dvc.lock` diffs human-readable in PR reviews, not adding a parallel tracking system.
>
> **Config drift detection vs. good commit discipline.** If every parameter change requires a commit message mentioning it (which the git rules already encourage), a separate drift detector is redundant. The real risk is silent changes slipping into unrelated commits — a pre-commit hook that flags "you changed a config file, is this intentional?" would be simpler.
>
> **The Polars question might answer itself.** With the sub-project split and the canonical `main()`, swapping pandas for Polars in one script becomes trivial. The instrumentation (timing, memory) is worth doing regardless. The "should we switch" decision can wait until there are numbers.
>
> **Missing from the brainstorm:**
>
> - **Revision workflow.** Both papers are under review — what happens when reviewers ask for changes? The sub-project split and submission branches need to play together. How does "rerun analysis with different clustering params" flow through the system?
> - **The next paper** (item 5). What would make the infrastructure investment pay off for paper #3? That's the real test of whether the sub-project architecture is worth building.

## Parked ideas

