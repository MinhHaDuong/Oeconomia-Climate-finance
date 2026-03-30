---
globs: ["content/**"]
---

# Writing Rules

## Core argument

Climate finance crystallized as an economic object by ~2009. Everything since has been fought within the categories established at that moment. This is intellectual history showing how economists create governable objects through quantification.

## Three-act periodization (data-driven)

- I. Before climate finance (1990–2006) — three disconnected traditions
- II. Crystallization (2007–2014) — structural breaks at 2007 (cosine) and 2013 (JS)
- III. The established field (2015–2025) — no further structural break

The periodization is endogenous (embedding-based break detection), not imposed from COP milestones. The core subset (most-cited papers) shows no structural break at all.

## Corpus

~28,400 works from OpenAlex + Semantic Scholar + ISTEX + bibCNRS + SciSpace + grey lit + teaching. Core subset: ~2,300 papers cited ≥ 50 times.

## Self-check questions

Before producing any substantial text:
1. Does this advance the core argument? (Climate finance as constructed economic object)
2. Is the economist's role visible? (Not just "institutions" or "policymakers")
3. Is this historically grounded? (Specific dates, documents, actors)
4. Does this fit Œconomia's interdisciplinary scope? (HET + STS + policy studies)
5. Will this interest both historians of economics AND climate policy scholars?

This is not a policy paper or a technical report. It's intellectual history.

## Voice and style

- Academic but accessible
- Historical narrative combined with analytical argument
- Avoid jargon; define terms when first introduced
- Show, don't just tell (use specific examples, names, dates)

## Things to avoid

- **Don't:** Write as if climate finance naturally exists. **Do:** Show how it was constructed.
- **Don't:** Assume categories are neutral or technical. **Do:** Analyze political implications of measurement choices.
- **Don't:** Oversimplify North-South divides. **Do:** Show specific actors and their motivations.

## Citation practices

- Cite primary sources with dates
- Name economists and institutions specifically (not "policymakers" but "OECD DAC")
- Include both academic and grey literature
- Track evolution of key terms across time
- Prioritize works that show economists' role in category-making
- Balance institutional documents with critical scholarship
- Include Global South perspectives

## AI tells to eliminate

### Blacklisted words (target: 0 occurrences)

delve, nuanced, multifaceted, pivotal, crucial, robust (unless statistical sense),
intricate, comprehensive, meticulous, vibrant, arguably, showcasing, underscores,
foster, tapestry, landscape (unless proper noun, e.g. CPI *Global Landscape*)

### Blacklisted phrases (target: 0 occurrences)

"it is important to note," "in the realm of," "stands as a testament to,"
"plays a vital role," "the landscape of," "navigating the complexities,"
"the interplay between," "sheds light on," "a growing body of literature,"
"offers a lens through which," "it is worth noting," "cannot be overstated"

### Density limits

- **Contrast farming** ("not X, but Y"): ≤3 justified instances per document. Each must be genuinely contrastive.
- **Em-dash density**: ≤2 per paragraph.
- **Sentence-initial "Moreover/Furthermore/Additionally"**: ≤2 per section.

### Other patterns to avoid

- Compulsive tricolons: not every list needs exactly three items
- Uniform sentence length: vary between short and long
- Excessive hedging: cut "perhaps," "it might be argued that," "to some extent"
- Over-explanation: trust the reader; cut "In other words," "That is to say,"

## Testing

`make check-fast` before editing. `make clean` then `make all` (separate Bash calls) as integration test before PR.

## When to ask the author

- Argument direction is genuinely ambiguous
- Multiple good sources conflict
- Author's position on controversial topic is unclear
