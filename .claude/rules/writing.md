---
globs: ["content/**"]
---

# Writing Rules

## Core argument

Climate finance crystallized as an economic object by ~2009. Everything since has been fought within the categories established at that moment. This is intellectual history showing how economists create governable objects through quantification.

## Three-act periodization (history, corpus-corroborated)

- I. Before climate finance (1990–2006) — three disconnected traditions
- II. Crystallization (2007–2014) — structural breaks at 2007 (cosine) and 2013 (JS)
- III. The established field (2015–2025) — no further structural break

The periodization is historically grounded and *corroborated* by embedding-based break detection — not the reverse. The detection is blind to the COP calendar, so finding the act I→II break at 2007/2009 independently of the policy timeline is corroboration, not circularity. The act II→III boundary is institutional: Paris (2015) shows only a marginal Jensen–Shannon rise, not a rupture, which is what the thesis predicts (post-2015 disputes occur within crystallized categories). Don't claim the periodization is "endogenous / not imposed from COP milestones" — that overclaims and contradicts the confirmatory framing. The core subset (most-cited papers) shows no structural break at all.

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

## CI test polarity rule

Prose adherence tests (`tests/test_manuscript_prose.py`) pin only **negative guards** (forbidden phrasings) and **mechanical checks** (density ratchets, structural presence). They never assert that a specific *positive* phrasing appears — positive pins break on every legitimate rewrite. The asymmetry: defects are lexically stable (an overclaim reads the same in any draft), good prose is not.

Positive editorial intent lives in `docs/editorial-brief.md` — one entry per standing decision (**Decision** / **Rationale** / **Ticket** / **Status**) — and is checked at review time by the `/review-pr-prose` brief auditor against each diff.

## Testing

`make check-fast` before editing. `make clean` then `make all` (separate Bash calls) as integration test before PR.

## When to ask the author

- Argument direction is genuinely ambiguous
- Multiple good sources conflict
- Author's position on controversial topic is unclear
