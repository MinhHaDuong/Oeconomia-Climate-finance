# Manuscript Plan (v4 — updated 2026-03-04)

**Target:** ~9,000 words for Œconomia "Varia" submission
**Source:** Extended abstract (submitted 2026-01-15) + computational results (technical-report.md)
**Pre-requisite:** Confirm with editor (language, length, timeline)

## Structural rationale

The breakpoint analysis detected two robust structural breaks (2007, 2013) and *no* break around 2015 or 2021. Censored-gap analysis (k=2) narrows this to a single dominant break at **2009** (Copenhagen). Lexical TF-IDF validation confirms 2009 produces a wholesale vocabulary reorientation; 2015 and 2021 are thematic inflections within an already-constituted field. The core subset (1,176 most-cited papers) shows **no structural break at all** — the categories were set early and never disrupted.

Thesis: climate finance crystallized as an economic object by ~2009. Everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought *within* the categories established at that moment.

## Phase 1 — Foundations (COMPLETE)

### 1.1 Paper figures

| # | Figure | File | Content |
|---|--------|------|---------|
| 1 | Emergence | `fig1_emergence.png` | Economics total + CF bars + share % (OpenAlex) |
| 2 | Breakpoints | `fig2_breakpoints.png` | JS + cosine divergence, breaks at 2007 & 2013 |
| 3 | Alluvial | `fig3_alluvial.{png,html}` | Thematic flows across 3 periods, 6 clusters |
| 4 | Seed axis | `fig4_seed_axis_core.png` | Efficiency↔accountability scatter, 1,176 core papers over time |
| 5 | Bimodality | `fig5a_bimodality.png` | KDE of eff/acc axis scores by period (ΔBIC=1,264) |

### Appendix figures

| File | Content |
|------|---------|
| `fig4_pca_scatter.png` | Unsupervised PCA bimodal axes, full corpus (3 panels) |
| `fig5a_bimodality_core.png` | Bimodality KDE on core (ΔBIC=112) |
| `fig5b_bimodality_lexical.png` | TF-IDF bimodality (ΔBIC=8,961) |
| `fig5c_bimodality_keywords.png` | Keyword co-occurrence scatter |
| `fig2b_breakpoints_core.png` | Breakpoints on core (no break except 2023 edge effect) |
| `fig2_breakpoints_censor{1,2}.png` | Censored breaks k=1 (2008,2013,2015), k=2 (2009 only) |
| `fig3b_alluvial_core.{png,html}` | Alluvial on core papers |
| `figA_1a_robustness.png` | Econ vs Finance vs RePEc overlap |
| `figA_lexical_tfidf_*.png` | Lexical validation at breakpoints |
| `figA_k_sensitivity.png` | k-sensitivity (k=4–7) |

### Key empirical findings for the manuscript

1. **Breaks at 2007 (cosine) and 2013 (JS)** — no break at Paris (2015) or Glasgow (2021)
2. **Censored k=2 singles out 2009** — Copenhagen as the dominant structural discontinuity
3. **Core shows no break** — the influential papers' thematic structure was established before 2007 and never disrupted; breaks are driven by the influx of new, lower-cited scholarship
4. **Bimodality is real** — efficiency↔accountability divide confirmed by embedding (ΔBIC=1,264), TF-IDF (ΔBIC=8,961), and keyword co-occurrence; present in core (ΔBIC=112 emb, 1,058 TF-IDF) but weaker
5. **Not the dominant axis** — the eff/acc divide is PC2, not PC1; the field's primary variance is something else (climate science vs. finance)
6. **Seed axis drift** — yearly median shifts from accountability side toward efficiency over time (visible in fig4_seed_axis_core)
7. **Venue structure** — core papers published in hybrid channels (journals + OECD/WB/IMF working papers), confirming institutional economists shaped categories through publication infrastructure

### 1.3 Manuscript compilation — DONE (PR #15)

- YAML front matter added (`title`, `subtitle`, `bibliography`, `csl`) — #9 T5
- Pandoc figure declarations added for Fig 1 and Fig 2 — #9 T5
- Note: `fig3_alluvial.png` is 1,035 px wide — below the ≥ 1,500 px journal requirement; regeneration needed

### 1.2 Bibliography audit — NOT STARTED

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
- Data support: both structural breaks (2007 cosine, 2013 JS) fall in this period; censored k=2 confirms 2009 (Copenhagen) as single dominant break; massive lexical reorientation at 2009
- Seed axis scatter (Fig 4): the yearly median shows the field's centre of gravity drifting toward efficiency throughout this period
- Venue support: core publication channels are already hybrid (journals + OECD/WB/IMF report/WP series), showing institutional economists shaping categories through publication infrastructures

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
- Data support: no structural break; core subset confirms categorical stability (no break 2005–2020); bimodality persists but within fixed poles
- Seed axis scatter (Fig 4): efficiency side grows denser but accountability pole remains occupied — the tension is constitutive, not resolved
- Venue support: continued OECD/World Bank/IMF presence in core report/WP channels

### Section IV: How Climate Finance Became an Economic Object — ~1,500 words
- Theoretical synthesis: commensuration → performativity → economization → boundary work
- Climate finance governable because made into economic object
- Economists as designers of policy-relevant knowledge (not just analysts)
- Kaul: global public goods require distinct financing logic
- The two-communities structure as constitutive tension (not bug, feature)
- What this case reveals about how economists create governable objects

### Introduction — PARTIALLY DRAFTED (PR #15)
- [x] Historiographical positioning expanded — pricing-instrument vs. accounting-instrument lineage, Roberts & Weikmans, Skovgaard — #7 A2
- [x] Corpus-as-exploratory-evidence caveat appended after GMM sentence — #6 A1
- [x] Figure declarations present (Fig 1 + Fig 2 via Pandoc syntax) — #9 T5
- [ ] Final pass (written last, after all body sections)

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

## Documentation files

| File | Purpose | Status |
|------|---------|--------|
| `CLAUDE.md` | Minimal AI handoff (data path, conventions, status) | Current |
| `AGENTS.md` | Writing guidelines, workflow rules, script commands | Current |
| `technical-report.md` | Full pipeline documentation (10 sections) | Current |
| `notes.md` | Working notes, draft arguments, empirical observations | Active |
| `extended abstract.md` | Submitted abstract (2026-01-15) | Archival |
