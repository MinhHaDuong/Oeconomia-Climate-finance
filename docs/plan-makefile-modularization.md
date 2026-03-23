# Plan: Makefile modularization into `makefile.d/`

Status: PLAN ONLY — do not modify the Makefile until this plan is reviewed.

## Motivation

The Makefile is 559 lines with three pipeline phases, archive packaging, quality
checks, and housekeeping all in one file. The braindump (2026-03-18) proposes
splitting it into `makefile.d/` with per-phase includes. The top-level Makefile
becomes a thin orchestrator defining contracts (phony targets), while each phase
gets its own `.mk` file with the real dependency graph.

## Proposed file layout

```
Makefile                       ← orchestrator (~80 lines)
makefile.d/
  phase1-corpus.mk             ← DVC workflow, corpus stages, corpus diagnostics
  phase2-analysis.mk           ← figures, tables, stats, all Phase 2 targets
  phase3-render.mk             ← Quarto render targets (manuscript, papers)
  archives.mk                  ← archive-analysis, archive-manuscript, archive-datapaper
  quality.mk                   ← check, check-fast, lint-prose, corpus-validate
```

## What stays in the root Makefile

| Section | Lines (current) | Content |
|---------|----------------|---------|
| Header comment | 1–16 | Three-phase pipeline description, usage block |
| Path variables | 18–34 | `DATA_DIR`, `BIB`, `CSL`, `SRC`, `UNIFIED` through `MOSTCITED` |
| Reproducibility exports | 36–39 | `PYTHONHASHSEED`, `SOURCE_DATE_EPOCH` |
| Include sets | 42–74 | `MANUSCRIPT_INCLUDES`, `TECHREP_INCLUDES`, `DATAPAPER_INCLUDES`, `COMPANION_INCLUDES`, `PROJECT_INCLUDES` |
| Figure sets | 76–91 | `MANUSCRIPT_FIGS`, `DATAPAPER_FIGS`, `COMPANION_FIGS`, `TECHREP_FIGS`, `ALL_FIGS` |
| `.PHONY` declaration | 94 | Single consolidated `.PHONY` line (or distributed — see Risks) |
| `.DEFAULT_GOAL` | 96 | `:= manuscript` |
| `SHELL` | 389 | `:= /bin/bash` (move to top) |
| `all` target | 98 | `all: manuscript papers` |
| `setup` target | 550–552 | Git hooks activation |
| `clean` target | 555–557 | `rm -rf output/` |
| `rebuild` target | 558 | `clean all` |
| Include directive | new | `include makefile.d/*.mk` |

**Key decision:** All shared variables (paths, file lists, include sets, figure
sets) stay in the root Makefile because multiple `.mk` files reference them.
This eliminates variable ordering problems.

## Target inventory per file

### `makefile.d/phase1-corpus.mk`

DVC workflow and corpus-building targets. Thin shim — most logic lives in `dvc.yaml`.

| Target | Current lines | Notes |
|--------|--------------|-------|
| `corpus` | 133–136 | Host-gated (`padme` only), runs `dvc repro` + `dvc push` |
| `corpus-sync` | 139–141 | Host-gated (not `padme`), `git pull` + `dvc pull` |
| `corpus-discover` | 145–146 | Alias for `dvc repro catalog_merge` |
| `corpus-enrich` | 148–149 | Alias for `dvc repro enrich_works ...` |
| `corpus-extend` | 151–152 | Alias for `dvc repro extend` |
| `corpus-filter` | 154–155 | Alias for `dvc repro filter` |
| `corpus-filter-all` | 157–158 | Alias for `dvc repro extend filter` |
| `corpus-align` | 160–161 | Alias for `dvc repro align` |
| `deploy-corpus` | 164–165 | `dvc push` |
| `content/tables/qa_citations_report.json` | 168–170 | Corpus diagnostic (reads enrichment caches) |

**Variables used:** `DATA_DIR` (from root).

### `makefile.d/phase2-analysis.mk`

The real dependency graph. This is the largest file (~200 lines).

| Target | Current lines | Notes |
|--------|--------------|-------|
| `check-corpus` | 181–186 | Gate: verify Phase 1 contract files exist |
| `check-manuscript-data` | 189–194 | Lighter gate (no citations needed) |
| `content/tables/tab_citation_coverage.md` | 200–201 | Corpus reporting table |
| `content/tables/tab_venues.md` | 203–204 | Venues table |
| `content/tables/tab_corpus_sources.csv` | 206–207 | Corpus sources export |
| `corpus-tables` | 209–210 | Grouped target |
| `$(STATS) &:` | 217–220 | Grouped target producing 4 vars.yml files |
| `stats` | 222 | Alias |
| `$(MOSTCITED)` | 227–228 | HET core subset |
| `content/tables/tab_core_venues_top10.md` | 230–231 | Core venues table |
| All figure targets | 237–355 | 20+ figure/table rules (manuscript, datapaper, companion, techrep, core variants, diagnostics) |
| `figures-manuscript` | 357 | |
| `figures-datapaper` | 358 | |
| `figures-companion` | 359 | |
| `figures-techrep` | 360 | |
| `figures` | 361 | |
| `lexical-figures` | 354–355 | `.PHONY` dynamic-output target |

**Variables used:** `DATA_DIR`, `REFINED`, `REFINED_EMB`, `REFINED_CIT`,
`MOSTCITED`, `STATS`, `ALL_FIGS`, `MANUSCRIPT_FIGS`, `DATAPAPER_FIGS`,
`COMPANION_FIGS`, `TECHREP_FIGS` (all from root).

### `makefile.d/phase3-render.mk`

Quarto render targets. Thin shim.

| Target | Current lines | Notes |
|--------|--------------|-------|
| `manuscript` | 367 | Phony: `output/content/manuscript.pdf output/content/manuscript.docx` |
| `papers` | 369 | Phony: three PDFs |
| `output/content/manuscript.pdf` | 371–372 | `quarto render --to pdf` |
| `output/content/manuscript.docx` | 374–375 | `quarto render --to docx` |
| `output/content/technical-report.pdf` | 377–378 | |
| `output/content/data-paper.pdf` | 380–381 | |
| `output/content/companion-paper.pdf` | 383–384 | |

**Variables used:** `SRC`, `BIB`, `CSL`, `MANUSCRIPT_FIGS`, `PROJECT_INCLUDES`,
`STATS` (all from root).

### `makefile.d/archives.mk`

Archive packaging for reviewers.

| Target | Current lines | Notes |
|--------|--------------|-------|
| `ANALYSIS_ARCHIVE`, `ANALYSIS_TMP`, `ANALYSIS_OUTPUTS` | 390–400 | Local variables (can move) |
| `archive-analysis` | 402–439 | Phase 2 reproducibility package |
| `MANU_ARCHIVE`, `MANU_TMP` | 446–447 | Local variables (can move) |
| `archive-manuscript` | 449–484 | Phase 3 reproducibility package |
| `DPAPER_ARCHIVE`, `DPAPER_TMP` | 490–491 | Local variables (can move) |
| `archive-datapaper` | 493–526 | Full pipeline package |

**Variables used:** `DATA_DIR`, `MANUSCRIPT_FIGS`, `MANUSCRIPT_INCLUDES`,
`ANALYSIS_OUTPUTS` (mixed root + local).

**Variables to move here:** `ANALYSIS_ARCHIVE`, `ANALYSIS_TMP`,
`ANALYSIS_OUTPUTS`, `MANU_ARCHIVE`, `MANU_TMP`, `DPAPER_ARCHIVE`, `DPAPER_TMP`
— these are archive-private and not referenced elsewhere.

### `makefile.d/quality.mk`

Quality gates and linting.

| Target | Current lines | Notes |
|--------|--------------|-------|
| `corpus-validate` | 196–197 | Runs `test_corpus_acceptance.py` |
| `check` | 529–530 | `lint-prose` + full pytest |
| `check-fast` | 533–534 | `lint-prose` + pytest (no slow markers) |
| `lint-prose` | 537–547 | Blacklisted words, em-dashes, contrast farming |

**Variables used:** `REFINED` (from root).

## Migration steps

### Step 0: Baseline

```bash
# Record current behavior as the test oracle
make -n all 2>&1 > /tmp/baseline-all.txt
make -n figures 2>&1 > /tmp/baseline-figures.txt
make -n manuscript 2>&1 > /tmp/baseline-manuscript.txt
make -n check 2>&1 > /tmp/baseline-check.txt
make -n archive-analysis 2>&1 > /tmp/baseline-archive.txt
make -p --no-builtin-rules 2>&1 > /tmp/baseline-db.txt
```

### Step 1: Create `makefile.d/` directory

```bash
mkdir -p makefile.d
```

### Step 2: Extract one file at a time, verify after each

For each `.mk` file, in this order:

1. **`quality.mk`** — smallest, fewest dependencies, safest first move.
2. **`phase1-corpus.mk`** — self-contained DVC shims.
3. **`archives.mk`** — self-contained packaging recipes.
4. **`phase3-render.mk`** — thin Quarto shims.
5. **`phase2-analysis.mk`** — largest, most interconnected, last.

After extracting each file:

```bash
# Verify: dry-run output must match baseline
make -n all 2>&1 | diff - /tmp/baseline-all.txt
make -n figures 2>&1 | diff - /tmp/baseline-figures.txt
make -n manuscript 2>&1 | diff - /tmp/baseline-manuscript.txt
make -n check 2>&1 | diff - /tmp/baseline-check.txt

# Verify: make database must match
make -p --no-builtin-rules 2>&1 | diff - /tmp/baseline-db.txt
```

### Step 3: Distribute `.PHONY`

Move the single consolidated `.PHONY` line into per-file declarations. GNU Make
merges multiple `.PHONY` declarations, so each `.mk` file declares its own
phony targets at the top. The root Makefile keeps `.PHONY` only for `all`,
`setup`, `clean`, `rebuild`.

### Step 4: Final verification

```bash
make check-fast          # tests pass
make -n all              # dry-run matches baseline
make -n archive-analysis # dry-run matches baseline
```

### Step 5: One commit per extraction

Each `.mk` extraction is a separate commit so that `git bisect` can isolate any
breakage. The commit sequence:

1. `refactor: extract makefile.d/quality.mk`
2. `refactor: extract makefile.d/phase1-corpus.mk`
3. `refactor: extract makefile.d/archives.mk`
4. `refactor: extract makefile.d/phase3-render.mk`
5. `refactor: extract makefile.d/phase2-analysis.mk`
6. `refactor: distribute .PHONY declarations per .mk file`

## Risks and mitigations

### 1. Variable ordering dependencies

**Risk:** An included `.mk` file references a variable defined in another `.mk`
file or later in the root Makefile.

**Mitigation:** All shared variables are defined in the root Makefile *before*
the `include` directive. Archive-private variables move into `archives.mk`.
No `.mk` file defines variables used by another `.mk` file.

### 2. Include order matters for target overrides

**Risk:** GNU Make's `include` with wildcards processes files in filesystem
order (locale-dependent). If two `.mk` files define the same target, the last
one wins silently.

**Mitigation:** No target is defined in more than one `.mk` file. The wildcard
`include makefile.d/*.mk` is acceptable because files are independent. If
ordering ever matters, switch to explicit includes:

```makefile
include makefile.d/phase1-corpus.mk
include makefile.d/phase2-analysis.mk
include makefile.d/phase3-render.mk
include makefile.d/archives.mk
include makefile.d/quality.mk
```

### 3. `.PHONY` fragmentation

**Risk:** Forgetting to declare a phony target in the new file, causing Make to
look for a file named after the target.

**Mitigation:** Each `.mk` file declares its `.PHONY` targets at the top.
The migration verification step compares `make -p` output to catch
discrepancies.

### 4. `SHELL` assignment placement

**Risk:** `SHELL := /bin/bash` is currently at line 389 (inside the archive
section). If it moves to `archives.mk`, other recipes lose bash features.

**Mitigation:** Move `SHELL := /bin/bash` to the root Makefile, near the top
(with the other global settings). This is a pre-existing issue — it should
already be at the top.

### 5. Grouped targets (`&:`) require GNU Make >= 4.3

**Risk:** Not a modularization risk per se, but worth noting: the grouped
target syntax (`&:`) in `phase2-analysis.mk` requires GNU Make >= 4.3.

**Mitigation:** Already a requirement of the current Makefile. No change needed.

### 6. `check-corpus` and `check-manuscript-data` placement

**Risk:** These gate targets are used by Phase 2 (`figures`) but could
logically belong in `quality.mk`.

**Decision:** Keep them in `phase2-analysis.mk` because they are prerequisites
of Phase 2 figure targets, not standalone quality checks. Placing them in
`quality.mk` would work technically (Make resolves cross-file dependencies) but
would obscure the Phase 2 dependency chain.

### 7. Editor/IDE support

**Risk:** Some editors don't follow `include` directives for Makefile syntax
highlighting or autocompletion.

**Mitigation:** Low severity. The `.mk` extension is widely recognized. Add a
modeline comment at the top of each file: `# vim: set ft=make :` or equivalent.

## Post-migration cleanup opportunities

- Add a header comment to each `.mk` file documenting its phase and contract.
- Consider whether `corpus-tables` belongs in Phase 1 or Phase 2 (currently
  Phase 2 because it reads `refined_works.csv`, not enrichment caches).
- The `lexical-figures` `.PHONY` declaration is currently separate from the
  main `.PHONY` line — this gets cleaned up naturally by distributing `.PHONY`.
