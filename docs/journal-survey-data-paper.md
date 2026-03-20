# Journal survey: Data paper target venues

Date: 2026-03-20

## Context

The climate finance corpus (29,878 works, 6 sources, multilingual, with embeddings)
needs a data paper — a standalone publication describing the dataset for reuse.
The companion methods paper (`companion-paper.qmd`) is a separate submission
targeting scientometrics journals.

## Journals evaluated

### 1. Scientific Data (Springer Nature)

- **Format**: Data Descriptor (dedicated article type)
- **APC**: ~€2,390 / $2,690 / £2,150
- **Impact factor**: 5.8 (2024), Q1
- **Open access**: Gold OA, CC BY 4.0
- **Data policy**: Dataset must be in a public, community-recognized repository
  (Zenodo qualifies). Release verified as condition of publication.
- **Required sections**: Title, Abstract, Background & Summary, Methods,
  Data Records, Technical Validation, Usage Notes, Code Availability,
  Author Contributions, Competing Interests, References
- **Key constraint**: "Data Descriptors should not contain results, discussion,
  or analyses." The goal is to describe data for reuse, not test hypotheses.
- **Word limit**: No explicit overall limit; Methods has no length cap.
  "Data Overview" limited to 1-2 figures and one paragraph.
- **Scope**: All disciplines including social sciences. Welcomes "big or small
  data, from new experiments or value-added aggregations of existing data."
- **Indexing**: Scopus, WoS, PubMed, DOAJ

**Fit assessment**: Excellent structural match — our `data-paper.qmd` already
follows the Data Descriptor template. The existing "Usage Notes" and
"Suggested applications" sections align well. Main gap: some analytical
content (structural breaks, bimodality results) in the current draft would
need to be removed or moved to the companion paper. The corpus *is* a
"value-added aggregation of existing data," which is explicitly in scope.
The multilingual design and embedding provision add value beyond a simple
database dump.

**Risk**: High APC (~€2,390). Need institutional or project funding.
Reviewer concern: social science bibliometric corpus may be seen as niche
for a journal that skews toward life/physical sciences.

### 2. Data Science Journal (CODATA/Ubiquity Press)

- **Format**: Research Paper or Practice Paper
- **APC**: £770 (~€900)
- **Impact factor**: Lower than Scientific Data
- **Open access**: Gold OA
- **Data policy**: Must have DOI in trusted repository. Reproducibility
  statement mandatory.
- **Required sections**: Title, Abstract (250 words max), Main text
  (introduction, methods, results, discussion, conclusion), Author
  contributions, Reproducibility statement, References
- **Word limit**: 8,000 words including references (Research Paper),
  3,000 words (Practice Paper)
- **Reference style**: Harvard (author-date)
- **Scope**: Data management, stewardship, curation, and policy.
  Explicitly welcomes data papers.

**Fit assessment**: Good alternative. Lower APC, data-focused scope.
The 8,000-word limit is tight but manageable. Unlike Scientific Data,
allows results/discussion, so we could include light analysis (corpus
statistics, coverage assessment) without splitting content. The
"reproducibility statement" requirement is well-served by our existing
documentation.

**Risk**: Lower prestige/IF than Scientific Data. The 8,000-word limit
(including references) may require significant trimming — our current
draft with includes is likely 5,000+ words before references.

### 3. JOSS (Journal of Open Source Software)

- **Format**: Software paper only
- **APC**: None (diamond OA)
- **Scope**: Research software with OSI-approved license. Does NOT accept
  data papers. Pre-trained models and notebooks are out of scope.

**Fit assessment**: Not suitable. JOSS is software-only.

**Eliminated.**

### 4. Quantitative Science Studies (MIT Press / ISSI)

- **Format**: Research article
- **APC**: $750 (ISSI members) / $1,200 (non-members)
- **Open access**: Gold OA
- **Data policy**: Must share data in public repository with DOI
- **Required sections**: Standard research article structure
- **Word limit**: Not explicitly stated; abstract max 200 words
- **Scope**: Quantitative studies of science and the scientific workforce.
  Theory and empirical work on science indicators, scholarly communication.

**Fit assessment**: Better for the companion/methods paper than for a pure
data descriptor. QSS readers want methodological contribution (the
embedding-based break detection framework), not dataset documentation.
The companion paper (`companion-paper.qmd`) is the right manuscript for QSS.

**Recommendation**: Target QSS with the companion paper, not the data paper.

### 5. Scientometrics (Springer)

- **Format**: Research article
- **APC**: Hybrid (subscription + OA option)
- **Scope**: Quantitative aspects of the science of science. Broad,
  established journal in the field.

**Fit assessment**: Like QSS, better for the methods paper. Could accept
a "dataset + methodology" hybrid, but pure data descriptors are not
their core article type.

## Recommendation

### Primary target: Scientific Data

The Data Descriptor format is purpose-built for our dataset. The existing
`data-paper.qmd` already follows the template. The high APC is a concern
but the journal's prestige and discoverability justify it if funding is
available. CNRS DIST may cover APCs for OA publications.

**Required changes to current draft:**
1. Remove analytical content (structural breaks, bimodality mentions) —
   these belong in the companion paper
2. Strengthen Technical Validation with quantitative metrics
3. Add Data Records section with precise file-by-file descriptions
4. Ensure Usage Notes focuses on reuse, not our own analyses
5. Add formal data availability statement pointing to Zenodo DOI

### Fallback: Data Science Journal (CODATA)

If APC is prohibitive or Scientific Data rejects, Data Science Journal
is a solid alternative with lower cost and explicit data paper scope.
The 8,000-word limit requires discipline but is achievable.

### Companion paper: QSS or Scientometrics

The methods paper (`companion-paper.qmd`) should target QSS or
Scientometrics separately. It cross-references the data paper but
stands alone as a methodological contribution.

## Journal-specific formatting constraints

### Scientific Data Data Descriptor

| Element | Constraint |
|---------|-----------|
| Abstract | 170 words max |
| Background & Summary | Accessible to non-specialists |
| Methods | No length limit; full reproducibility |
| Data Records | File-by-file description, schema |
| Technical Validation | Quantitative quality measures |
| Usage Notes | Reuse guidance, not our analyses |
| Code Availability | Script descriptions, repo link |
| Figures | Up to ~8; must be self-explaining |
| Tables | As needed; describe data structure |
| References | Nature style (numbered, superscript) |
| Data | Must be in public repository (Zenodo) |
| No results/discussion | Analyses belong elsewhere |

### Data Science Journal (fallback)

| Element | Constraint |
|---------|-----------|
| Abstract | 250 words max |
| Total length | 8,000 words including references |
| Sections | Standard (intro, methods, results, discussion) |
| References | Harvard style (author-date) |
| Reproducibility | Formal statement required |
| Data | DOI in trusted repository |
