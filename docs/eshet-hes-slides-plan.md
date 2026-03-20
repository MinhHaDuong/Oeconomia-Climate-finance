# ESHET-HES 2026 Conference Slides Plan

Date: 2026-03-20

## Conference context

- **Event**: ESHET-HES Joint Conference (first ever joint conference)
- **Dates**: May 26-29, 2026 in Nice (Universite Cote d'Azur)
- **Theme**: "Economists under Pressure and the Political Limits to Economics"
- **Status**: Abstract accepted (submitted Jan 2026, accepted Feb 2026)
- **Deadline for slides**: ~mid-May (2 months from now)
- **Talk format**: Standard paper presentation (likely 20-30 min + discussion)

## Theme alignment

The conference theme asks: how have political pressures shaped, constrained,
or transformed the production of economic knowledge?

Our paper answers this directly for climate finance:
- Economists at OECD/World Bank built accounting categories (Rio markers,
  mobilised finance methodologies) under pressure from competing political
  demands: North wanting credit for existing flows, South wanting additionality
- The resulting categories were deliberately ambiguous — a political resource,
  not a technical failure
- Pressure produced not distortion but a specific kind of economic knowledge:
  accounting categories designed to be "good enough" for all sides

## Audience

HET scholars + science studies + some policy scholars. ~200 delegates.
They know Pigou, Coase, Nordhaus. They do NOT know:
- Rio markers, ODA tagging, Article 4.3 UNFCCC
- The $100bn accounting dispute details
- Embedding-based bibliometrics

The talk must make the climate finance story accessible to an HET audience
while demonstrating that it belongs in the history of economics, not just
in policy studies.

## Slide structure (draft, ~25 minutes)

### 1. Opening hook (2 slides, 2 min)
- The $300bn Baku number: what does it measure?
- "No institution holds this sum. No ledger records it. No methodology
  for counting it commands consensus."
- Question: how did climate finance become countable?

### 2. Why HET should care (2 slides, 3 min)
- Existing HET of climate economics: Nordhaus, Stern, IAMs (Pottier 2016)
- Missing chapter: accounting, not modelling. Commensuration (Espeland &
  Stevens), not optimisation.
- Conference theme fit: economists under pressure to produce *usable*
  categories, not *correct* models

### 3. Act I — Before climate finance (2 slides, 3 min)
- Article 4.3 UNFCCC (1992): "new and additional," "incremental costs"
- Three disconnected traditions: environment economics, development finance,
  financial economics
- No unified object called "climate finance"

### 4. Act II — Crystallization (3 slides, 5 min)
- Bali 2007 → Copenhagen 2009: the $100bn commitment
- OECD Rio markers: Corfee-Morlot's statistical infrastructure
- The efficiency ↔ accountability divide emerges
- Corpus evidence: structural break at 2007-2009 (not 2015)

### 5. Act III — Disputes within stable categories (3 slides, 5 min)
- Four controversies: loans, markers, mobilised finance, ODA boundary
- All fought within categories established during crystallization
- Paris 2015 changes volume, not structure
- Corpus evidence: no structural break at 2015 or 2021

### 6. The argument (2 slides, 3 min)
- Strategic ambiguity as political resource (not technical failure)
- From Article 4.3's legal precision to deliberately vague categories
- Economists produced governability through ambiguity

### 7. Method note (1-2 slides, 2 min)
- Brief: ~30,000 works, 6 sources, multilingual embeddings
- Endogenous periodization corroborates historical narrative
- Reflexive note: our method is itself an act of commensuration

### 8. Discussion opening (1 slide, 2 min)
- What other economic objects were built through accounting rather than
  modelling? (GDP, inflation, poverty lines...)
- Does the "economists under pressure" framing apply to other cases
  of category-making?

## Figures to reuse from the manuscript

1. **fig_bars.png**: Publication volume by period — shows the three acts
2. **fig_composition.png**: Thematic composition evolution — shows
   crystallization and stability
3. **UMAP semantic map** (from tech report): visual proof of clustering

## Figures to create for slides

4. **Timeline**: key events + publication volume overlay
   - UNFCCC 1992 → Kyoto 1997 → Bali 2007 → Copenhagen 2009 →
     Paris 2015 → Glasgow 2021 → Baku 2024
5. **Efficiency ↔ accountability diagram**: visual representation of
   the two poles with key actors/institutions on each side
6. **Four controversies table**: loans, markers, mobilised finance,
   ODA boundary — with the tension in each

## Format options

### A. Quarto Reveal.js (recommended)
- Already in the Quarto ecosystem
- Web-based, portable
- Can include interactive UMAP if desired
- Easy to version control

### B. LaTeX Beamer
- Traditional academic format
- HET audience may expect this
- Harder to include interactive elements

### C. PowerPoint/LibreOffice
- Maximum formatting control
- But not version-controllable

**Recommendation**: Quarto Reveal.js. It's consistent with the project's
tooling, produces clean academic slides, and can be rendered to PDF for
backup.

## Next steps

1. Create `content/slides-eshet.qmd` with Reveal.js format
2. Draft slide content following the structure above
3. Reuse existing figures (fig_bars, fig_composition)
4. Create new timeline and pole diagram figures
5. Practice talk timing (~25 min target)
6. Get author feedback on emphasis and framing

## Open questions for the author

1. **Talk duration**: confirm 20, 25, or 30 minutes
2. **Audience pitch**: how technical should the computational method be?
   (The HET audience likely cares about the history, not the embeddings)
3. **Figure priority**: which existing figures are most effective for a
   live presentation?
4. **French or English?** Nice is France, but ESHET-HES is international.
   Probably English, but confirm.
5. **Conference proceedings**: will there be a proceedings volume? If so,
   does it require a separate paper or can we submit the Oeconomia manuscript?
