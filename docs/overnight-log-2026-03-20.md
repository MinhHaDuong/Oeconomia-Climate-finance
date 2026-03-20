# Overnight exploration log — 2026-03-20

## Balance summary

| Category | Work items | Approx % |
|----------|-----------|----------|
| Deliverable (paper/slides) | PR #243 (data paper journal survey + draft alignment), PR #244 (ESHET-HES slides draft + plan) | 95% |
| Tooling | None | 0% |
| Meta (planning/braindumps) | This log, braindump below | 5% |

Balance rule satisfied: deliverable work at 95%, well above the 60% minimum.
No tooling tickets were worked — PRs #231-#235 already handle the red tests.

## PRs opened

| PR | Branch | Type | Status |
|----|--------|------|--------|
| #243 | `data-paper-journal-survey` | Deliverable | Open for review |
| #244 | `eshet-hes-slides-exploration` | Deliverable | Open for review |

## Decisions made

### 1. Data paper journal target: Scientific Data (Nature)

Surveyed 5 journals: Scientific Data, Data Science Journal (CODATA), JOSS,
QSS, Scientometrics.

- **JOSS eliminated**: software-only, does not accept data papers
- **QSS and Scientometrics**: better for the companion methods paper
- **Scientific Data**: Data Descriptor format matches existing draft structure;
  "value-added aggregations" explicitly in scope; high prestige (IF 5.8)
- **Data Science Journal**: fallback if APC (EUR 2390) is prohibitive

Alternative considered: submitting to QSS as a combined "data + methods" paper.
Rejected because Scientific Data's no-analysis constraint and QSS's methods
focus mean the two papers serve fundamentally different audiences (data reusers
vs methods innovators) and cannot be meaningfully combined.

### 2. Companion paper: QSS as primary target

QSS offers: right scope (quantitative scientometrics), fully open access,
lower APCs ($750-1200), ISSI community as natural audience.

Scientometrics is fallback (more established but hybrid OA, higher cost).

### 3. Sequential submission recommended

Data paper first (establishes dataset credibility independently), then
companion paper with data paper DOI. Author may prefer parallel submission
for speed.

### 4. ESHET-HES slides: Reveal.js format, HET audience pitch

Conference theme "Economists under Pressure" aligns perfectly with the paper's
argument. Slides open with the $300bn Baku hook, keep computational method to
one slide, and close with discussion questions connecting to the conference theme.

Quarto Reveal.js chosen over Beamer or PowerPoint for consistency with project
tooling and version control.

### 5. Data paper draft aligned with Scientific Data constraints

Removed analytical content (structural breaks, bimodality) from Technical
Validation. Added abstract (123/170 words), Data Availability section,
expanded Code Availability. Strengthened relevance validation description
with cross-encoder AUC and human validation metrics.

## What worked

- **Journal survey approach**: WebSearch + WebFetch gave enough information to
  make informed decisions about all 5 journals. The key insight (JOSS is
  software-only) saved time.
- **Existing draft quality**: The data-paper.qmd was already well-structured.
  Alignment with Scientific Data required ~40 lines of changes, not a rewrite.
- **Conference theme alignment**: The ESHET-HES theme is a gift for this paper.
  The slides practically write themselves when you frame "economists under
  pressure" as "economists building deliberately ambiguous accounting categories."

## What surprised me

- **Scientific Data blocks web scraping**: nature.com returns 303/403 for direct
  fetch. Had to use WebSearch + third-party mirrors (Scribd, GitHub templates)
  to reconstruct the guidelines. The christopherkenny/scientific-data Quarto
  template on GitHub was the most useful source.
- **Background & Summary max 700 words**: more restrictive than expected. Our
  current 395 words is fine, but adding context for a social science audience
  (most Scientific Data papers are in life/physical sciences) might push toward
  the limit.
- **ESHET-HES submission was already closed**: deadline was January 16, 2026.
  The abstract was accepted in February. The task is slides preparation, not
  submission. Two months remain (conference May 26-29).

## Open questions for the author

### Data paper
1. **Primary target**: Scientific Data (APC ~EUR 2390) vs Data Science Journal (~GBP 770)?
2. **Submission timing**: sequential or parallel with companion paper?
3. **Repository**: make GitHub repo public now or upon acceptance?
4. **Co-authors**: single-author or add contributors?
5. **Nearest-neighbour validation claim**: run script or soften language?

### ESHET-HES slides
6. **Talk duration**: 20, 25, or 30 minutes?
7. **Computational method depth**: one slide? two? demo?
8. **Language**: English (assumed) or French?
9. **Proceedings**: separate paper needed?

### Strategy
10. **Reading plan**: ROADMAP mentions Tier 1 reading. Should overnight sessions
    explore this, or is it author-only work?

## Braindump: new ideas from tonight's exploration

### Data paper as infrastructure investment

The data paper is not just a publication — it's infrastructure for the next
phase. Once published with a DOI, it becomes citable by:
- The companion methods paper (QSS)
- The Oeconomia paper (cross-reference in revision)
- Future papers by others who want to study climate finance bibliometrically

This means the data paper should be designed for maximum reusability, not
just for our own analyses. The "field boundary studies" reuse potential
(how different databases define "climate finance" differently) is genuinely
novel and could attract citation from information science.

### Poster option at ESHET-HES

The conference accepts posters alongside papers. If the talk slot is short
(20 min) or if the author wants to present the computational method in
more depth, a companion poster showing the UMAP map, the three-act
clustering, and the efficiency-accountability axis could work well.
Posters are described as "more direct and informal one-on-one interaction"
and can present "digital platforms, exploratory work, or databases" —
exactly what the corpus is.

### Data paper as "living dataset"

Scientific Data accepts updates to existing Data Descriptors when the
dataset grows. If the corpus is periodically refreshed (annual OpenAlex
update, new grey literature), a version 2 could be published later.
This argues for designing the pipeline and documentation with updateability
in mind — which it already is (incremental embeddings, append-only pool).

### Preprint strategy

QSS "strongly encourages" preprinting each version. The data paper could
go on Zenodo (already deposited) + arXiv (cs.DL) or SSRN. The companion
paper could go on arXiv (cs.DL or cs.CL). This gives both papers
discoverability before peer review.

## Feedback memories

- **WebFetch vs WebSearch**: for journal guidelines, WebSearch is more
  reliable than WebFetch because publisher sites often block direct
  access. Use WebSearch first, then WebFetch only for accessible pages.
- **Scientific Data template**: the christopherkenny/scientific-data
  Quarto extension on GitHub provides exact formatting. Consider
  installing it for the actual submission.
