# Writing Guidelines

Consult this file when editing manuscript prose, bibliography, or literature review.

## Core argument

Climate finance crystallized as an economic object by ~2009. Everything since has been fought within the categories established at that moment. This is intellectual history showing how economists create governable objects through quantification.

## Three-act periodization (data-driven)

- I. Before climate finance (1990–2006) — three disconnected traditions
- II. Crystallization (2007–2014) — structural breaks at 2007 (cosine) and 2013 (JS)
- III. The established field (2015–2025) — no further structural break

The periodization is endogenous (embedding-based break detection), not imposed from COP milestones. The core subset (most-cited papers) shows no structural break at all.

## Corpus

~28,400 works from OpenAlex + Semantic Scholar + ISTEX + bibCNRS + SciSpace + grey lit + teaching. Core subset: ~2,300 papers cited ≥ 50 times.

## When to ask the author (manuscript-specific)

### Ask when
- Argument direction is genuinely ambiguous
- Multiple good sources conflict
- Author's position on controversial topic is unclear

### Don't ask when
- Standard academic practices apply
- You can research the answer
- It's a matter of stylistic preference you can reasonably infer

## Self-check questions

Before producing any substantial text:
1. Does this advance the core argument? (Climate finance as constructed economic object)
2. Is the economist's role visible? (Not just "institutions" or "policymakers")
3. Is this historically grounded? (Specific dates, documents, actors)
4. Does this fit Œconomia's interdisciplinary scope? (HET + STS + policy studies)
5. Will this interest both historians of economics AND climate policy scholars?

This is not a policy paper or a technical report. It's intellectual history that uses climate finance as a case study for understanding how economists create governable objects through quantification.

## Voice and style

- Academic but accessible
- Historical narrative combined with analytical argument
- Avoid jargon; define terms when first introduced
- Show, don't just tell (use specific examples, names, dates)

## Things to avoid

- **Don't:** Write as if climate finance naturally exists
- **Do:** Show how it was constructed through specific choices
- **Don't:** Assume categories are neutral or technical
- **Do:** Analyze political implications of measurement choices
- **Don't:** Oversimplify North-South divides
- **Do:** Show specific actors and their motivations

## Citation practices

- This is a history paper: cite primary sources with dates
- When discussing controversies, present multiple perspectives fairly
- Name economists and institutions specifically (not "policymakers" but "OECD DAC")
- Include both academic and grey literature (reports, policy papers)

## Literature review priorities

- Prioritize works that show economists' role in category-making
- Balance institutional documents (OECD, UNFCCC) with critical scholarship
- Include Global South perspectives (avoid OECD-centric bias)
- Track evolution of key terms across time

## Search strategies

### ISTEX corpus
Search for:
- Specific economists: "Stern", "Corfee-Morlot"
- Methodological terms: "Rio marker", "grant equivalent", "mobilized finance"
- Institutions: "OECD DAC", "Standing Committee on Finance", "Climate Policy Initiative"
- Temporal markers: "Copenhagen", "Paris Agreement", "100 billion"

### SciSpace reports
The SciSpace reports in `ai-tech-reports/SciSpace/` contain:
- Pre-identified key works on specific topics
- CSV files with structured data
- `Quick_Reference_Must_Cite_and_Overlooked_Works.md` for literature gaps

## Testing

Verification commands are the "tests" for prose. Before editing, run `make check-fast`. After editing, confirm it still passes. `make clean && make all` is the integration test — run before opening a PR.

## Quality standards

### For draft sections
- Every empirical claim needs a source
- Every "turning point" needs a date and specific actors
- Balance description (what happened) with analysis (why it matters)
- Connect micro-level details to macro-level argument

### For final review
- Check that "history of economic thought" framing is prominent
- Verify all citations are in bibliography
- Ensure Œconomia style guidelines are followed (see `.agent/guidelines/oeconomia-style.md`)
- Confirm word count fits journal norms

## Language polish — AI tells to eliminate

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

Reference: Liang et al. 2024, "Mapping the Increasing Use of LLMs in Scientific Papers" (arXiv:2406.07016)
