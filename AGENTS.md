# AI Agent Guidelines for Climate Finance History Project

See `README.md` for project overview, current status, research corpus, and theoretical framework.
See `PLAN.md` for the manuscript action plan (structure, word budgets, figures).
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
The ISTEX corpus can be used for:
- Bibliometric analysis (frequency of terms, co-citation networks)
- Discourse analysis (how "climate finance" is defined across time)
- Author network analysis (who are the key scholars/practitioners?)

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
- **Use feature branches** for new work (e.g., `corpus-pipeline`, `bibliometric-analysis`)
- Merge to `main` when a milestone is stable
- Always commit before starting a new phase of work
- Propose a commit when a logical unit of work is complete

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
