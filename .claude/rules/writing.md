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

## Ghost mode

Write in *The Economist* style: clear, direct, concrete, no filler. No AI tells.
Internalize this — don't mechanically check a list while drafting.
The `/review-pr-prose` panel includes a dedicated AI-tells auditor with full wordlists (`config/ai-tells.yml`).

## Testing

`make check-fast` before editing. `make clean` then `make all` (separate Bash calls) as integration test before PR.

## When to ask the author

- Argument direction is genuinely ambiguous
- Multiple good sources conflict
- Author's position on controversial topic is unclear
