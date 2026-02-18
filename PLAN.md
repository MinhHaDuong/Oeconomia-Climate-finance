# Manuscript Plan

**Target:** ~9,000 words for Œconomia "Varia" submission
**Source:** Extended abstract (submitted 2026-01-15) + notes.md outline
**Pre-requisite:** Confirm with editor (language, length, timeline)

## Phase 1 — Foundations

### 1.1 Bibliometric figures (from ISTEX corpus metadata)

**Figure 1: The emergence of "climate finance" in academic literature (1990-2024)**
- Bar chart of 484 ISTEX articles by publication year
- Annotate key events: Rio 1992, Copenhagen 2009 ($100bn pledge), Paris 2015, Glasgow 2021, NCQG 2024
- Source: ISTEX JSON metadata (`publicationDate` field, all 484 articles dated)
- Point: climate finance as a research object barely exists before 2009, peaks around Paris

**Figure 2: Two intellectual communities in climate finance scholarship**
- Co-authorship or keyword network from ISTEX metadata (1,293 unique authors, keywords/subjects available)
- Visualize the market-failure cluster (OECD/MDB-affiliated, leverage/mobilization keywords) vs. political-economy cluster (accountability/equity/justice keywords)
- Alternative: simpler table mapping key authors to institutional affiliations and theoretical orientation
- Source: ISTEX JSON metadata (`author`, `keywords.teeft`, `categories` fields)

### 1.2 Bibliography audit

- Cross-check `bibliography/main.bib` against `AI tech reports/SciSpace/Quick_Reference_Must_Cite_and_Overlooked_Works.md`
- Ensure primary sources present: Corfee-Morlot (Rio markers), Michaelowa (over-reporting), Weikmans & Roberts (accounting disputes), Stern (HLPF 2010), Kaul (global public goods)
- Add key OECD/UNFCCC reports as grey literature entries

## Phase 2 — Drafting (section by section)

Each section expands from the extended abstract, using SciSpace analyses and ISTEX corpus for evidence.

### Section I: Before Climate Finance (1990-2005) — ~1,500 words
- Intellectual pre-history: Ayres & Kneese, externalities framework
- Development economics categories: DAC, concessionality, grant-equivalent
- Climate economics: Nordhaus, Manne, Stern, Weitzman — models, not money
- Negishi weights and burden-sharing disconnected from aid debates
- Why climate finance doesn't yet exist as an autonomous object
- Theory: Desrosières (commensuration), Porter (trust in numbers)

### Section II: The Defining Moment (2009-2015) — ~2,000 words
- Copenhagen $100bn as performative promise (Callon, MacKenzie)
- Jan Corfee-Morlot and OECD Rio markers: building statistical infrastructure
- Battle OECD vs. UNFCCC for operational definition
- Emergence of key concepts: public climate finance, mobilized private finance, leverage ratios
- Stern and the UN HLPF 2010: economists as architects
- Theory: performativity, boundary work

### Section III: Metrisation and Contestation (2015-2021) — ~2,000 words
- Paris Agreement transparency frameworks
- UNFCCC Standing Committee on Finance as counter-knowledge producer
- Grant-equivalent vs. face value (Oxfam vs. OECD)
- Michaelowa on incentive-driven over-reporting of Rio markers
- Weikmans & Roberts: accounting disputes as distributive conflicts
- Additionality, double counting, non-concessional loans
- Climate finance as professionalized field with routines, careers, metrics
- Theory: economization (Fourcade, Çalışkan)

### Section IV: Field Closure and NCQG (2021-2025) — ~1,500 words
- Glasgow: "the $100bn will be met" — claim resting on statistical infrastructure
- OECD validates; Global South contests
- DAC categories become official language of climate despite development origins
- Shift to $300bn NCQG at Baku
- Theory: boundary work, infrastructures of quantification

### Section V: How Climate Finance Became an Economic Object — ~1,500 words
- Theoretical synthesis: commensuration → performativity → economization → boundary work
- Climate finance governable because made into economic object
- Economists as designers of policy-relevant knowledge (not just analysts)
- Kaul: global public goods require distinct financing logic
- What this case reveals about how economists create governable objects

### Introduction (written last) — ~700 words
- Frame contribution for Œconomia readership (HET + STS + policy)
- State thesis clearly
- Announce periodization and method

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
