# Manuscript Plan (v4 — updated 2026-03-04)

**Target:** ~9,000 words for Œconomia "Varia" submission
**Source:** Extended abstract (submitted 2026-01-15) + computational results (technical-report.md)
**Pre-requisite:** Confirm with editor (language, length, timeline)
**Current word count:** ~9,600 rendered (8,500 markdown)

## Structural rationale

The breakpoint analysis detected two robust structural breaks (2007, 2013) and *no* break around 2015 or 2021. Censored-gap analysis (k=2) narrows this to a single dominant break at **2009** (Copenhagen). Lexical TF-IDF validation confirms 2009 produces a wholesale vocabulary reorientation; 2015 and 2021 are thematic inflections within an already-constituted field. The core subset (1,176 most-cited papers) shows **no structural break at all** — the categories were set early and never disrupted.

Thesis: climate finance crystallized as an economic object by ~2009. Everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought *within* the categories established at that moment.

## Phase 1 — Foundations (COMPLETE)

### 1.1 Paper figures (COMPLETE)

| # | Figure | File | Content |
|---|--------|------|---------|
| 1 | Emergence | `fig1_emergence.png` | Economics total + CF bars + share % (OpenAlex) |
| 2 | Breakpoints | `fig2_breakpoints.png` | JS + cosine divergence, breaks at 2007 & 2013 |
| 3 | Alluvial | `fig3_alluvial.{png,html}` | Thematic flows across 3 periods, 6 clusters |
| 4 | Seed axis | `fig4_seed_axis_core.png` | Efficiency↔accountability scatter, 1,176 core papers over time |
| 5 | Bimodality | `fig5a_bimodality.png` | KDE of eff/acc axis scores by period (ΔBIC=1,264) |

### Appendix figures (COMPLETE)

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

### 1.2 Bibliography audit (COMPLETE)

- `scripts/verify_bibliography.py`: 26/47 SciSpace references matched in `main.bib`
- Primary sources confirmed: Corfee-Morlot, Michaelowa, Roberts & Weikmans, Stern, Kaul
- 47 entries in `main.bib`, all cited in manuscript

## Phase 2 — Drafting (COMPLETE)

All sections drafted, numbered per Œconomia style (Arabic, not Roman).

### Introduction — ~900 words
- Opening hook: the puzzle of debating hundreds of billions that no institution holds
- HET + STS framing for Œconomia readership
- Thesis statement, three-act periodization, method overview
- Corpus description (22,000 works, 7 sources, endogenous break detection)
- Road map (Sections 1–4)

### Section 1: Before Climate Finance (1990–2006) — ~1,500 words
- 1.1 Environmental economics and the externality framework
- 1.2 Development economics and statistical infrastructure
- 1.3 Burden-sharing and the disconnection from finance
- 1.4 Why climate finance did not yet exist

### Section 2: Crystallization (2007–2014) — ~2,500 words
- 2.1 The Copenhagen moment
- 2.2 Building statistical infrastructure: Rio markers and OECD accounting
- 2.3 Two communities, one object
- 2.4 The efficiency–accountability divide as structural feature

### Section 3: The Established Field (2015–2025) — ~2,500 words
- 3.1 The Paris framework and the transparency turn
- 3.2 The four controversies
- 3.3 From $100 billion to $300 billion

### Section 4: How Climate Finance Became an Economic Object — ~1,500 words
- Theoretical synthesis: commensuration → performativity → economization
- The two-communities structure as constitutive tension

### Conclusion — ~500 words
- Three findings: constructed (not discovered), never disrupted, structurally divided
- The real battle is over definitions, not amounts

## Phase 3 — Revision (IN PROGRESS)

### Done
- [x] Œconomia house style applied (see `docs/oeconomia-style.md`)
  - Dot-separated title, French subtitle, small-caps author
  - No Introduction heading, Arabic numbered sections (1. / 1.1), unnumbered Conclusion
  - Submission header, date, corresponding author footnote (LaTeX via `header-includes`)
- [x] AI-tell sweep (blacklisted words, em-dash density, contrast farming)
- [x] Bibliography verification (47 entries, all cited)
- [x] Code audit (all 7 scripts pass, byte-reproducible pipeline)
- [x] PDF + ODT build clean (no warnings)

### Remaining
- [ ] Content polish pass (currently editing: opening hook, figure cross-references)
- [ ] French abstract (Résumé)
- [ ] Keywords (FR + EN)
- [ ] Final word count trim if needed (currently ~9,600 rendered, target ~9,000)
- [ ] Proofread bibliography formatting (DOI on separate line per Œconomia style)
- [ ] Final `make clean && make all` + visual check
- [ ] Move current draft to `release/` for submission
- [ ] Consider restructuring: consolidate quantitative material into a dedicated section
  - Move intro paragraph "We ground this historical argument..." + Figures 1–2
  - Move §2.5 (publication infrastructure) and §2.6 (efficiency–accountability divide)
  - Rationale: separates the historical narrative (§1–3) from the computational evidence
  - Trade-off: cleaner structure vs. losing the current integration of data within narrative

## Phase 4 — Submission packaging (NOT STARTED)

- [ ] Tag repo `v1.0-submission` + push tag
- [ ] Archive on Zenodo (via GitHub integration) → get DOI
- [ ] Upload `technical-report.md` to HAL as working paper → get HAL ID
  - Must include breakpoint analysis evidence (figures, method description) — the manuscript
    cites structural breaks repeatedly but never shows the divergence plots or method details.
    The HAL working paper is the minimum credible home for this evidence;
    alternatively, a companion methods paper (see below) would be the stronger venue.
- [ ] Add "Data and code availability" paragraph to manuscript (before Bibliography)
- [ ] Draft cover letter pointing reviewers to HAL + Zenodo
- [ ] Companion methods paper (Scientometrics/QSS): parked for post-acceptance
  - Stronger case now: the Œconomia manuscript leans heavily on breakpoint results
    it cannot fully present. A peer-reviewed companion would let us cite it properly.

## Build

```bash
make all          # builds manuscript.pdf + manuscript.odt
make clean        # removes PDF + ODT
```

## Documentation files

| File | Purpose | Status |
|------|---------|--------|
| `CLAUDE.md` | AI handoff (data path, conventions, status) | Current |
| `AGENTS.md` | Writing guidelines, workflow rules, script commands | Current |
| `docs/oeconomia-style.md` | Œconomia house style (eyeballed from 15-4 samples) | Current |
| `technical-report.md` | Full pipeline documentation (10 sections) | Current |
| `notes.md` | Working notes, draft arguments, empirical observations | Active |
| `extended abstract.md` | Submitted abstract (2026-01-15) | Archival |
