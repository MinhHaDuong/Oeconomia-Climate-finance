# AI Agent Guidelines for Climate Finance History Project

See `CLAUDE.md` for data paths, current state, and next implementation tasks.
See `PLAN.md` for the manuscript action plan (three-act structure, five figures).
See `method.md` for the detailed computational analysis plan.
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
- Ensure Œconomia style guidelines are followed (see `docs/Informations aux auteurs.md`)
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

## Self-Check Questions

Before producing any substantial text:
1. Does this advance the core argument? (Climate finance as constructed economic object)
2. Is the economist's role visible? (Not just "institutions" or "policymakers")
3. Is this historically grounded? (Specific dates, documents, actors)
4. Does this fit Œconomia's interdisciplinary scope? (HET + STS + policy studies)
5. Will this interest both historians of economics AND climate policy scholars?

---

**Remember:** This is not a policy paper or a technical report. It's intellectual history that uses climate finance as a case study for understanding how economists create governable objects through quantification.
