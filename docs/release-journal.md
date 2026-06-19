# Release Journal

Journal format, most recent first.

---

## 2026-03-30 — Corpus v1.1.1 (text normalization, unreleased)

**What changed**: Added a text normalization step at the merge funnel point (`catalog_merge.py`) to fix encoding artifacts inherited from upstream aggregator APIs. No new data harvested; no API calls.

**Fixes applied** (via `normalize_text()` in `pipeline_text.py`):

| Issue | Rows affected | Fix |
|-------|---------------|-----|
| HTML named entities (`&amp;`, `&lt;`) | ~1,200 titles + ~1,000 abstracts | `html.unescape()` |
| HTML numeric entities (`&#13;`, `&#146;`) | ~770 abstracts | `html.unescape()` |
| Literal `\n`/`\t` in text | ~1,070 abstracts | Replace with space |
| Zero-width chars (ZWSP, soft-hyphen, BOM) | ~80 across fields | Strip |
| Mojibake / double-encoded UTF-8 (`Ã©` → `é`) | ~65 across fields | `ftfy.fix_text()` |
| Smart-quote mojibake (`â€™` → `'`) | ~40 abstracts | `ftfy.fix_text()` |

**Not fixed**: 29 records (0.09%) with U+FFFD replacement characters in author names — encoding errors at the publisher metadata deposit level, present in both OpenAlex and Crossref APIs.

**Expected downstream impact** (after `dvc repro`):
- ~18 additional title+year dedup merges (previously missed because `R&amp;D` ≠ `R&D`)
- ~37.8% of abstracts change (mostly curly-quote→straight-quote normalization by ftfy)
- Embeddings recomputed → UMAP/clustering may shift
- Frozen v1 data (`config/v1_*`) and submitted manuscripts are unaffected

**New dependency**: `ftfy` 6.3.1

**PR**: #534, **Issue**: #533

### GROBID citation parsing (#538)

352K unstructured Crossref citation strings parsed into structured fields (title, author, year) via GROBID 0.8.1 running locally in podman. 30 minutes for the full run at 200 citations/sec.

| Metric | Count | Rate |
|--------|-------|------|
| Unique strings parsed | 351,978 | 100% |
| Output rows | 355,016 | — |
| Titles filled | 355,016 | 100% |
| Authors filled | 297,288 | 84% |
| Years filled | 342,078 | 96% |

Results cached in `enrich_cache/grobid_parsed.jsonl` (keyed by text hash). `merge_citations.py` reads `ref_parsed.csv` as third input alongside Crossref and OpenAlex caches. New DVC step in `enrich_citations` stage.

**PR**: #561, **Issue**: #538

### Fuzzy ref matching (#539)

GROBID-parsed refs matched against refined_works.csv using rapidfuzz token_sort_ratio ≥ 85 with year ±1 blocking. 3,414 new citation graph edges discovered — previously invisible references to IPCC reports, UNFCCC, Paris Agreement, Stern Review, etc.

**PR**: #565, **Issue**: #539

### Crossref DOI fallback (#569)

`enrich_dois.py` now queries Crossref when OpenAlex returns no DOI match. Removed the `is_oa_only` skip that was hiding 8,920 works from DOI resolution. Tested on 20 works: 15% hit rate. Full run (~9,268 works, ~8.5 hours) pending.

**PR**: #570, **Issue**: #569

### Pipeline re-run results

| Metric | v1.1 | v1.1.1 |
|--------|------|--------|
| Raw works | 42,922 | 42,916 |
| Refined works | 31,713 | 31,712 |
| Citations | 968,871 | 967,204 |
| Refined citations | — | 834,221 |

---

## 2026-03-26 — Submitted to RDJ4HSS (data paper)

**Target**: Research Data Journal for the Humanities and Social Sciences
**Platform**: platform.openjournals.nl/RDJHSS
**Document**: `content/data-paper.qmd`

**Status**: Under review (peer reviewers + data specialists).

**Cover letter**: `release/2026-03-26 RDJ4HSS/CoverLetter.txt`
**Checklist**: `release/rdj-submission-checklist.md`
**Submission branch**: `submission/rdj-data-paper`
**Git tag**: `v1.1-rdj-submitted`

**Zenodo deposit**: https://doi.org/10.5281/zenodo.19236130
- Single reproducibility archive: corpus v1.1 + pipeline source code
- Links to v1.0 deposit (10.5281/zenodo.19097045)

**Known errata in as-sent cover letter**: corpus stats cite v1.0 numbers
(42,368 raw / 31,204 refined / 929,014 citations) instead of v1.1
(42,922 / 31,713 / 968,871). The paper itself uses correct v1.1 numbers.

---

## 2026-03-18 — Submitted to Oeconomia (Varia)

**Platform**: https://oeconomia-hmp.fr (OJS)

**Uploaded**:
- Anonymized manuscript PDF (shows [Anonymous], [repository URL removed for review])
- fig_bars.png and fig_composition.png (separate files, >=1500px, 300 dpi)
- Cover letter (see `release/2026-03-18 Oeconomia/cover letter.txt`)
- AI disclosure statement (see `release/2026-03-18 Oeconomia/Use of AI statement.txt`)
- Metadata: English + French abstracts, English + French keywords, JEL codes B20/Q54/F35/Q56

**Zenodo deposit**: https://doi.org/10.5281/zenodo.19097045
- Two reproducibility archives: analysis (56 MB) + manuscript (683 KB)
- Both tested on two independent machines before upload

**HAL deposit**: hal-05558422v1
- Manuscript PDF uploaded; tarballs not duplicated (already on Zenodo)
- Affiliation: CIRED (UMR 8568)

**Git tag**: `v1.0-submission`

**What was NOT done** (from submission-plan.md):
- §2 Reading plan: ongoing — Tier 1 books partially read, work continues
- §3A LLM validation: Claude review done; GPT-4/Gemini cross-review not done
- §3B CIRED colleague validation: not done before submission (decided to submit first, use conference feedback instead — Option A from §4)
- Conference slides (§4): to prepare by mid-May for ESHET-HES Nice (May 26–29)

---

## 2026-02-16 — Decision on special issue submission

Francesco Sergi (managing editor) replied: paper not selected for the special issue "History of Climate Economics" (~50 submissions received), but encouraged to submit as Varia contribution "at your earliest convenience."

Full decision letter: `release/2026-01-14 Special Issue on Climate Economics/20260216 decision.txt`

Key quote: "considering the quality of your proposal [...] and its relevance with respect to the general scope of Oeconomia, we encourage you to consider submitting your paper to our journal, independently from the special issue, as a 'Varia' contribution."

---

## 2026-01-15 — Extended abstract submitted to special issue

Submitted extended abstract "History of climate finance as an economic object: accounting categories, controversies, and economists as policy experts" to Oeconomia's special issue "History of Climate Economics."

Full text: `release/2026-01-14 Special Issue on Climate Economics/extended abstract.md`

---

## 2025-11-26 — Editor guidance received

Initial guidance from editor on special issue scope and requirements.

See: `release/2026-01-14 Special Issue on Climate Economics/2025-11-26 email guidance editor.txt`

---

## Context

The special issue call "History of Climate Economics" was the initial target. After the abstract was not selected for the special issue but received encouragement from the managing editor, the strategy shifted to submitting the full manuscript as a Varia contribution. The ESHET-HES conference (Nice, May 2026) where the abstract was accepted provides a parallel venue.

**Cover letter** (as sent):
See `release/2026-03-18 Oeconomia/cover letter.txt`

**AI disclosure** (as sent):
See `release/2026-03-18 Oeconomia/Use of AI statement.txt`
