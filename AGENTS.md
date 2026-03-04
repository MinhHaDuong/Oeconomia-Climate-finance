# AI Agent Guidelines for Climate Finance History Project

See `CLAUDE.md` for data paths and current status.
See `PLAN.md` for the manuscript action plan (three-act structure, five figures).
See `technical-report.md` for the full data pipeline documentation.
See `notes.md` for working notes and the original detailed outline.

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
The full corpus (~22,000 works from OpenAlex + ISTEX + Scopus + grey lit) supports:
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
- Working drafts: Markdown (`.md`); final submission: ODT or DOCX
- Convert with Pandoc: `pandoc input.md -o output.odt`
- Bibliography: `bibliography/main.bib`, author-date style
- Version control: old versions in `attic/`, submissions in `release/`

### Dependency management
- **Always use `uv sync`** to install dependencies. Never use `pip` or `uv pip`.
- All dependencies are declared in `pyproject.toml` at project root.
- torch is pinned to CPU-only builds via `[tool.uv.sources]` (no NVIDIA/CUDA).
- To add a dependency: edit `pyproject.toml`, then run `uv sync`.

### Running scripts

Always use `uv run`. All scripts support `--no-pdf` to skip PDF generation.
```bash
# Data collection (slow — API calls)
uv run python scripts/count_openalex_econ_cf.py                  # OpenAlex econ yearly
uv run python scripts/count_openalex_econ_cf.py --scope finance  # OpenAlex finance yearly
uv run python scripts/count_openalex_econ_fin_overlap.py         # Econ/Finance overlap (ID sets)
uv run python scripts/count_repec_econ_cf.py                     # RePEc yearly (needs local mirror)

# Figures
uv run python scripts/plot_fig1_emergence.py     # Fig 1 (reads openalex_econ_yearly.csv)
uv run python scripts/plot_fig1_robustness.py    # Fig A.1a (reads all yearly + overlap CSVs)
uv run python scripts/analyze_alluvial.py        # Fig 2 + Fig 3 (full corpus)
uv run python scripts/analyze_alluvial.py --core-only   # Fig 2b + Fig 3b (core: cited ≥ 50)
uv run python scripts/analyze_alluvial.py --robustness  # k-sensitivity appendix
uv run python scripts/analyze_alluvial.py --censor-gap 1  # Censored breaks (k=1)
uv run python scripts/analyze_alluvial.py --censor-gap 2  # Censored breaks (k=2)
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
grep -ciE 'delve|nuanced|multifaceted|pivotal|tapestry|intricate|meticulous|vibrant|showcasing|underscores' manuscript.md

# Em-dash heavy paragraphs (expect 0 lines with 3+)
grep -cP '---.*---.*---' manuscript.md

# Contrast farming (expect ≤3)
grep -cP 'not .{3,60}, but ' manuscript.md
```

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
