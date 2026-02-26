# Manuscript Plan (v2 — three-act structure)

**Target:** ~9,000 words for Œconomia "Varia" submission
**Source:** Extended abstract (submitted 2026-01-15) + notes.md outline + breakpoint analysis results
**Pre-requisite:** Confirm with editor (language, length, timeline)

## Structural rationale (new in v2)

The breakpoint analysis detected two robust structural breaks (2007, 2013) and *no* break around 2015 or 2021. Lexical TF-IDF validation confirms only 2009 produces a wholesale vocabulary reorientation; 2015 and 2021 are thematic inflections within an already-constituted field. This merges old Sections III and IV into one.

Thesis: climate finance crystallized as an economic object by ~2009. Everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought *within* the categories established at that moment.

## Phase 1 — Foundations

### 1.1 Bibliometric figures (5 figures, see method.md v2)

**Figure 1: The emergence of climate finance in economics (1990–2025)** — NEW
Three time series on common timeline:
1. Economics publications in OpenAlex (the denominator)
2. Publications with "climate" in title in OpenAlex (broader climate-in-economics literature)
3. Climate finance publications in our corpus

Shows climate finance emerging as a specific *economic* object after Copenhagen, not from climate science generally.

**Figure 2: Structural break detection** — breakpoints figure (formerly Fig 2a)
Z-scored JS divergence, detected breaks at 2007 and 2013. No break at 2015 or 2021.

**Figure 3: Thematic recomposition** — alluvial diagram (formerly Fig 2b)
Community flows across data-derived periods (1990–2006, 2007–2012, 2013–2014, 2015–2025).

**Figure 4: Citation genealogy** — genealogy DAG (formerly Fig 3)
Time-ordered citation structure of intellectual communities.

**Figure 5: Testing the two-communities hypothesis** — NEW
Bimodality along efficiency↔accountability axis, both semantic and lexical.

### 1.2 Bibliography audit

- Cross-check `bibliography/main.bib` against `AI tech reports/SciSpace/Quick_Reference_Must_Cite_and_Overlooked_Works.md`
- Ensure primary sources present: Corfee-Morlot (Rio markers), Michaelowa (over-reporting), Weikmans & Roberts (accounting disputes), Stern (HLPF 2010), Kaul (global public goods)
- Add key OECD/UNFCCC reports as grey literature entries

## Phase 2 — Drafting (three-act structure)

### Section I: Before Climate Finance (1990–2006) — ~1,500 words
- Intellectual pre-history: Ayres & Kneese, externalities framework
- Development economics categories: DAC, concessionality, grant-equivalent
- Climate economics: Nordhaus, Manne, Stern, Weitzman — models, not money
- Negishi weights and burden-sharing disconnected from aid debates
- Why climate finance doesn't yet exist as an autonomous object
- Theory: Desrosières (commensuration), Porter (trust in numbers)
- Data support: formative phase, sparse literature, pre-Copenhagen vocabulary (CDM, Kyoto, development aid)

### Section II: Crystallization (2007–2014) — ~2,500 words
Merges the "defining moment" with the first consolidation. Two detected breaks bracket this period.

- Copenhagen $100bn as performative promise (Callon, MacKenzie)
- Jan Corfee-Morlot and OECD Rio markers: building statistical infrastructure
- Battle OECD vs. UNFCCC for operational definition
- Emergence of key concepts: public climate finance, mobilized private finance, leverage ratios
- Stern and the UN HLPF 2010: economists as architects
- The 2013 consolidation: field categories stabilize, metrics become routine
- Two communities crystallize: efficiency pole (OECD/MDB leverage) vs. accountability pole (Oxfam/CARE justice)
- Theory: performativity, boundary work
- Data support: both structural breaks (2007 cosine, 2013 JS) fall in this period; massive lexical reorientation at 2009

### Section III: The Established Field (2015–2025) — ~2,500 words
Merges old Sections III (Metrisation) and IV (NCQG). No further breaks detected.

- Paris Agreement transparency frameworks
- UNFCCC Standing Committee on Finance as counter-knowledge producer
- Grant-equivalent vs. face value (Oxfam vs. OECD)
- Michaelowa on incentive-driven over-reporting of Rio markers
- Weikmans & Roberts: accounting disputes as distributive conflicts
- Additionality, double counting, non-concessional loans
- Climate finance as professionalized field with routines, careers, metrics
- Glasgow: "the $100bn will be met" — claim resting on statistical infrastructure
- OECD validates; Global South contests
- DAC categories become official language of climate despite development origins
- Shift to $300bn NCQG at Baku
- Key point: all these disputes happen *within* stable intellectual categories
- Theory: economization (Fourcade, Çalışkan), boundary work, infrastructures of quantification
- Data support: no structural break; 2015 and 2021 are thematic inflections, not ruptures

### Section IV: How Climate Finance Became an Economic Object — ~1,500 words
- Theoretical synthesis: commensuration → performativity → economization → boundary work
- Climate finance governable because made into economic object
- Economists as designers of policy-relevant knowledge (not just analysts)
- Kaul: global public goods require distinct financing logic
- The two-communities structure as constitutive tension (not bug, feature)
- What this case reveals about how economists create governable objects

### Introduction (written last) — ~700 words
- Frame contribution for Œconomia readership (HET + STS + policy)
- State thesis clearly
- Announce three-act periodization and method (endogenous break detection)

### Conclusion — ~500 words
- Without stabilized categories, no governable financing
- The $100bn→$300bn transition depends on pre-existing economic tools
- The real battle is over definitions, not amounts
- Implications for future climate finance architecture

## Phase 3 — Revision

- Run AGENTS.md self-check (5 questions)
- Style pass: Œconomia author-date conventions (see `docs/Informations aux auteurs.md`)
- Word count check (~8,000-10,000 target)
- Convert: `pandoc manuscript.md --citeproc --bibliography=bibliography/main.bib -o manuscript.odt`
- Upload as "revision" on Œconomia platform
