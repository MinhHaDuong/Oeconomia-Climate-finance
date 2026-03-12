# AI Agent Guidelines for Climate Finance History Project

> **Do NOT modify `CLAUDE.md`.** It contains only `@AGENTS.md` and must stay that way. All instructions and status live here in `AGENTS.md`.

See `README.md` for project overview, repository structure, data paths.
See `PLAN.md` for the manuscript action plan (three-act structure, five figures).
See `content/technical-report.qmd` for the full data pipeline documentation.

## Status (2026-03-11)

- Manuscript: ~9,400 words, 47 bib entries, 2 figures + 1 table
- Corpus: 30,085 refined works, 29,252 with embeddings, 2,284 core
- Citation graph: 775,288 rows, 74% corpus coverage
- Quarto: 4 documents, 11 shared includes, cross-refs (`@fig-*`, `@tbl-*`)
- Fig 1 (bars): self-explaining legend, grayscale, 120mm, starts 1992, caption updated
- Fig 2 (composition): horizontal stacked % bars, Oeconomia style — may relocate to §3–4
- Table 2 (poles): efficiency vs accountability terms — done
- Table 1 (traditions): BLOCKED — co-citation communities merge after 2007
- Peer-review simulation docs archived in `docs/peer-review-simulation-20260310/`
- **Next priorities**:
  1. Human proofread of full manuscript
  2. Corpus update ongoing (enrichment pipeline)
  3. Regen Fig 2 — consider relocating to §3 or §4
  4. Table 1 — tradition detection for §1.5, or relocate to conclusion
  5. Regen period detection curves + terms table for §2.5
  6. Quantitative support for efficiency–accountability tension in §3.4
  7. Redistribute quantitative method details across sections/footnotes/annex

## Project Structure

This is a Quarto multi-document project (`_quarto.yml`). Four outputs share
reusable fragments in `content/_includes/` via `{{< include >}}` directives:

- `content/manuscript.qmd` — main Œconomia article (self-contained, no includes)
- `technical-report.qmd` — pipeline documentation (composed entirely of includes)
- `data-paper.qmd` — corpus data paper (reuses corpus-construction + reproducibility)
- `companion-paper.qmd` — methods companion (reuses all analysis sections)

Build with `make manuscript` (PDF + DOCX) or `make papers` (3 companion PDFs).
`make all` builds everything. See `Makefile` for targets.

## Writing Guidelines

- Academic but accessible
- Historical narrative combined with analytical argument
- Avoid jargon; define terms when first introduced
- Show, don't just tell (use specific examples, names, dates)

## Task-Specific Guidance

### Literature Review
- Prioritize works that show economists' role in category-making
- Balance institutional documents (OECD, UNFCCC) with critical scholarship
- Include Global South perspectives (avoid OECD-centric bias)
- Track evolution of key terms across time

### Data Analysis
The full corpus (~30,000 works from OpenAlex + ISTEX + Scopus + grey lit) supports:
- Bibliometric analysis (publication volume, co-citation networks, community detection)
- Embedding-based analysis (structural breaks, semantic clustering, bimodality)
- Lexical analysis (TF-IDF validation, term emergence)
- Discourse analysis (how "climate finance" is defined across time)

The three-act periodization is **data-driven** (endogenous break detection), not imposed from COP milestones:
- I. Before climate finance (1990–2006)
- II. Crystallization (2007–2014) — breaks at 2007 and 2013
- III. The established field (2015–2025) — no further breaks

### Citation Practices
- This is a history paper: cite primary sources with dates
- When discussing controversies, present multiple perspectives fairly
- Name economists and institutions specifically (not "policymakers" but "OECD DAC")
- Include both academic and grey literature (reports, policy papers)

## Things to Avoid

- **Don't:** Write as if climate finance naturally exists
- **Do:** Show how it was constructed through specific choices
- **Don't:** Assume categories are neutral or technical
- **Do:** Analyze political implications of measurement choices
- **Don't:** Oversimplify North-South divides
- **Do:** Show specific actors and their motivations

## Search Strategies

### Finding Relevant Passages in ISTEX Corpus
Search for:
- Specific economists: "Stern", "Corfee-Morlot"
- Methodological terms: "Rio marker", "grant equivalent", "mobilized finance"
- Institutions: "OECD DAC", "Standing Committee on Finance", "Climate Policy Initiative"
- Temporal markers: "Copenhagen", "Paris Agreement", "100 billion"

### Working with AI Analyses
The SciSpace reports in `AI tech reports/SciSpace/` contain:
- Pre-identified key works on specific topics
- CSV files with structured data
- `Quick_Reference_Must_Cite_and_Overlooked_Works.md` for literature gaps

## Quality Standards

### For Draft Sections
- Every empirical claim needs a source
- Every "turning point" needs a date and specific actors
- Balance description (what happened) with analysis (why it matters)
- Connect micro-level details to macro-level argument

### For Final Review
- Check that "history of economic thought" framing is prominent
- Verify all citations are in bibliography
- Ensure Œconomia style guidelines are followed (see `docs/oeconomia-style.md`)
- Confirm word count fits journal norms

## Communication with Author

### When to Ask
- Argument direction is genuinely ambiguous
- Multiple good sources conflict
- Author's position on controversial topic is unclear

### When Not to Ask
- Standard academic practices apply
- You can research the answer
- It's a matter of stylistic preference you can reasonably infer

## Technical Notes

### Git versioning
- **Hooks**: checked into `hooks/`. After cloning, run `git config core.hooksPath hooks`.
  The pre-commit hook rejects changes to `CLAUDE.md` (must stay `@AGENTS.md`).
- **Commit frequently** — do not let work accumulate without versioning
- **Use worktrees** for feature branches — work in isolated copies via `git worktree`, not `git stash`/`git checkout`. This preserves uncommitted work on `main` and enables parallel ticket work.
- **One branch per ticket**, named `t{N}-short-description` (e.g., `t3-censored-breaks`)
- **Create PRs** for each ticket so the author can review changes before merging
- Merge to `main` when a milestone is stable
- Always commit before starting a new phase of work
- Propose a commit when a logical unit of work is complete

### Autonomous workflow
When working on multiple tickets:
1. Launch each ticket in its own worktree (Agent tool with `isolation: "worktree"`)
2. Independent tickets run in parallel
3. Push each branch and create a PR with summary + test plan
4. Clean up worktree branches after pushing named branches

### File management
- Working drafts: Quarto Markdown (`.qmd`); final submission: PDF or DOCX
- Build with `make` (calls `quarto render` under the hood)
- Shared fragments live in `content/_includes/` — edit there, all documents update
- Bibliography: `content/bibliography/main.bib`, author-date style
- Version control: old versions in `attic/`, submissions in `release/`

### Conventions
- `uv sync` to install (never pip). `uv run python scripts/...` to execute.
- All scripts support `--no-pdf`.
- `make` builds all documents. `make manuscript` builds manuscript only. `make papers` builds the 3 companion documents. `make figures` regenerates all figures (byte-reproducible).
- House style: `docs/oeconomia-style.md` (eyeballed from 15-4 samples)

### Dependency management
- **Always use `uv sync`** to install dependencies. Never use `pip` or `uv pip`.
- All dependencies are declared in `pyproject.toml` at project root.
- torch is pinned to CPU-only builds via `[tool.uv.sources]` (no NVIDIA/CUDA).
- To add a dependency: edit `pyproject.toml`, then run `uv sync`.

### Data location
- Data lives **outside the repo**, at the path set by `CLIMATE_FINANCE_DATA` in `.env`.
- `scripts/utils.py` reads `.env` and exports `DATA_DIR`, `CATALOGS_DIR`, `EMBEDDINGS_PATH`. Never hardcode `data/catalogs/` relative to the repo — it doesn't exist there.

### Running scripts

Always use `uv run`. All scripts support `--no-pdf` to skip PDF generation.

### Pipeline phases

The pipeline has three phases with a strict contract between them:

**Phase 1 — Corpus building** (slow, API-dependent, run rarely):
- Scripts: `catalog_*`, `enrich_*`, `qa_*`, `qc_*`, `corpus_*`
- Four steps with intermediate artifacts in `$CLIMATE_FINANCE_DATA/catalogs/`:
  1. **corpus-discover**: merge sources → `unified_works.csv`
  2. **corpus-enrich**: enrich DOIs/abstracts/citations on `unified_works.csv` → `enriched_works.csv`
  3. **corpus-extend**: flag all works (no rows removed) → `extended_works.csv`
  4. **corpus-filter**: apply policy, audit → `refined_works.csv` (final Phase 1 output)
- Phase 1 → Phase 2 **contract**: `refined_works.csv`, `embeddings.npz`, `citations.csv`
- Run with: `make corpus` (all four steps) or individual targets

**Phase 2 — Analysis & figures** (fast, deterministic, run often):
- Scripts: `analyze_*`, `plot_*`, `compute_*`, `export_*`, `summarize_*`, `build_het_core.py`
- Reads ONLY Phase 1 outputs; produces `content/figures/` and `content/tables/`
- Run with: `make figures`

**Phase 3 — Render** (Quarto → PDF/DOCX):
- Run with: `make manuscript` or `make papers`

```bash
# Citation enrichment (run in order; both are resumable)
uv run python scripts/enrich_citations_batch.py                  # Crossref references (do first)
uv run python scripts/enrich_citations_openalex.py               # OpenAlex referenced_works (fills gap)
uv run python scripts/qc_citations.py                            # Verify citation quality (30-sample)
# Or simply: make citations  (runs all three in order)

# Figures
uv run python scripts/compute_alluvial.py        # Compute tables (full corpus)
uv run python scripts/plot_fig_breakpoints.py    # fig_breakpoints.png (reads tab_breakpoints.csv)
uv run python scripts/plot_fig_alluvial.py       # fig_alluvial.png + HTML (reads tab_alluvial.csv)
uv run python scripts/compute_alluvial.py --core-only          # Tables (core: cited ≥ 50)
uv run python scripts/plot_fig_breakpoints.py --core-only      # fig_breakpoints_core.png
uv run python scripts/plot_fig_alluvial.py --core-only         # fig_alluvial_core.png
uv run python scripts/compute_alluvial.py --robustness         # k-sensitivity appendix
uv run python scripts/compute_alluvial.py --censor-gap 1       # Censored breaks (k=1)
uv run python scripts/compute_alluvial.py --censor-gap 2       # Censored breaks (k=2)
# Legacy: analyze_alluvial.py still works as a thin wrapper calling all three scripts
uv run python scripts/analyze_bimodality.py      # Fig 5a/5b/5c
uv run python scripts/analyze_bimodality.py --core-only  # Fig 5a/5b/5c (core: cited ≥ 50)
uv run python scripts/plot_fig45_pca_scatter.py --core-only --supervised  # Fig 4 seed axis (paper)
uv run python scripts/plot_fig45_pca_scatter.py  # Fig 4 PCA scatter (appendix, full corpus)
uv run python scripts/analyze_genealogy.py       # Fig 4 genealogy (depends on bimodality output)
uv run python scripts/summarize_core_venues.py   # Core venue tables + institution summaries
uv run python scripts/export_core_venues_markdown.py  # Manuscript-ready top-10 venue markdown table
```

## Language Polish — AI Tells to Eliminate

This manuscript was co-written with an LLM. Apply these rules on every edit pass.

### Blacklisted words (target: 0 occurrences)

delve, nuanced, multifaceted, pivotal, crucial, robust (unless statistical sense),
intricate, comprehensive, meticulous, vibrant, arguably, showcasing, underscores,
foster, tapestry, landscape (unless proper noun, e.g. CPI *Global Landscape*)

### Blacklisted phrases (target: 0 occurrences)

"it is important to note," "in the realm of," "stands as a testament to,"
"plays a vital role," "the landscape of," "navigating the complexities,"
"the interplay between," "sheds light on," "a growing body of literature,"
"offers a lens through which," "it is worth noting," "cannot be overstated"

### Contrast farming (target: ≤3 justified instances)

Pattern: "not X, but Y" used for rhetorical emphasis.
Each instance must be genuinely contrastive (a real either/or), not decorative.
Rephrase decorative contrasts with "rather than," "instead of," or restructure.

### Em-dash density (target: ≤2 per paragraph)

Convert excess em-dash parentheticals to:
- Actual parentheses: `(X, Y, Z)` for lists
- Commas or semicolons for clause-level asides
- Periods for genuinely separate thoughts

### Other patterns to avoid

- **Compulsive tricolons**: not every list needs exactly three items
- **Uniform sentence length**: vary between short and long
- **Excessive hedging**: cut "perhaps," "it might be argued that," "to some extent"
- **Over-explanation**: trust the reader; cut "In other words," "That is to say,"
- **Sentence-initial "Moreover/Furthermore/Additionally"**: use sparingly (≤2 per section)

### Verification command

```bash
# Blacklisted words (expect 0)
grep -ciE 'delve|nuanced|multifaceted|pivotal|tapestry|intricate|meticulous|vibrant|showcasing|underscores' content/manuscript.qmd

# Em-dash heavy paragraphs (expect 0 lines with 3+)
grep -cP '---.*---.*---' content/manuscript.qmd

# Contrast farming (expect ≤3)
grep -cP 'not .{3,60}, but ' content/manuscript.qmd
```

### Citation Graph

`citations.csv` (775,288 rows) was built from two sources:

- **Crossref** (`enrich_citations_batch.py`): covers papers where publishers deposit reference lists
- **OpenAlex** (`enrich_citations_openalex.py`): fills the gap using `referenced_works`

**Overall coverage**: 17,248 / 23,194 corpus DOIs (74%) appear as source papers.
**Core coverage** (cited ≥ 50): 2,284 core works.
**Quality**: precision = recall = 1.000 verified against Crossref on 30-paper sample.
**Structural ceiling**: the remaining 22% are at publishers (preprints, small journals, regional outlets) with no API reference metadata. Next step: PDF OCR with GROBID for core papers.

The OpenAlex enrichment uses a two-phase approach:
1. Batch-fetch `referenced_works` (list of OpenAlex IDs) for each corpus DOI via filter endpoint
2. Batch-resolve OpenAlex IDs → DOIs + title/year/journal via `openalex:W1|W2|...` filter

Both scripts are resumable: Crossref uses `.citations_batch_checkpoint.csv`, OpenAlex uses `.citations_oa_done.txt`.

### Intellectual Traditions (Table 1) — Status

Empirical detection via co-citation community detection is implemented (`analyze_cocitation.py`, `compare_communities_across_windows.py`). Analysis across four time windows (pre-2007, pre-2015, pre-2020, full) reveals:

- Pre-2007: 18 small, distinct communities — econometrics, institutions, adaptation, aid, CDM, etc.
- Pre-2015: merger into mega-community (97 papers), modularity drops to 0.14
- Post-2020: re-crystallizes into 6 stable communities (Q=0.45): climate risk, governance, adaptation, Paris, green bonds, earth systems

Only the governance/accountability lineage (DiMaggio → Keohane → Weikmans) persists across all four windows. With the enriched citation graph (78% coverage), re-running the co-citation analysis should yield stronger community signal, especially for the pre-2007 period.

**Table 1 is still pending**: the user's interpretation maps pre-2007 communities 1-2 = environmental economics, 3-4 = burden-sharing, 5 = aid/CDM. Needs final write-up after re-running with enriched data.

Reference: Liang et al. 2024, "Mapping the Increasing Use of LLMs in Scientific Papers" (arXiv:2406.07016)

## Self-Check Questions

Before producing any substantial text:
1. Does this advance the core argument? (Climate finance as constructed economic object)
2. Is the economist's role visible? (Not just "institutions" or "policymakers")
3. Is this historically grounded? (Specific dates, documents, actors)
4. Does this fit Œconomia's interdisciplinary scope? (HET + STS + policy studies)
5. Will this interest both historians of economics AND climate policy scholars?

---

**Remember:** This is not a policy paper or a technical report. It's intellectual history that uses climate finance as a case study for understanding how economists create governable objects through quantification.
