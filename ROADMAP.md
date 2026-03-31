# Roadmap

## North star

Climate finance crystallized as an economic object by ~2009. Everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought within the categories established at that moment. This paper traces how economists and institutions co-produced those categories.

## Current milestone: Under review

Submitted to Oeconomia (Varia) on 2026-03-18. Waiting for referee reports (~3 months).

- [ ] Prepare ESHET-HES conference slides (Nice, May 26–29, 2026)
- [ ] Continue Tier 1 reading plan (defence against reviewer questions)
- [ ] Companion methods paper (Scientometrics/QSS): parked for post-acceptance

## Next milestone: Data paper

Submit data paper to RDJ4HSS (diamond OA). Immediate priority.

- [ ] Finalize and submit data paper (PDF ready at `output/content/data-paper.pdf`)

## Then: Transfer to AEDIST

Before this repo can serve the AEDIST project, the reusable harness must be split out.

- [ ] Extract harness into standalone repo (#391)
- [ ] Offline ticket system — good to have (PR #385)

## Post-submission improvements

- [x] Split embeddings encoding (Phase 1) from UMAP+clustering (Phase 2) (#189)
- [x] Split remaining enrich stages into independent DVC stages (#428)
- [x] Re-enable Semantic Scholar with API key (#263)
- [x] Add `in_v1` provenance column for v1.0 backward compatibility (#283)
- [ ] JETP query: add concept filter to exclude physics journal noise

## Completed

- **Submission packaging (2026-03-18)**: Zenodo (DOI 10.5281/zenodo.19097045), HAL (hal-05558422v1), git tag v1.0-submission, cover letter + AI disclosure, figures ≥1500px
- **Revision**: proofread, word count trim (9,600→8,860), final build + visual check, release/
- Foundations: figures, bibliography audit, empirical findings
- Drafting: all sections (intro, §1–§4, conclusion)
- Œconomia house style, AI-tell sweep, code audit, PDF+ODT build clean
- Doc restructuring: separated concerns (AGENTS → workflow only, domain guidance → docs/), added Dragon Dreaming + TDD + git hooks
- Agent-agnostic skills: `.claude/skills/`, make check, AGENTS.md works with any AI assistant
- Harness consolidation (#457): `docs/` guidelines + `runbooks/` → `.agent/` → `.claude/rules/` + `.claude/skills/`
- Agent identity (#109): machine user `HDMX-coding-agent`, classic PAT in `.env`, convention documented in AGENTS.md
- DVC integration (#101–#104, #109): data versioning, pipeline DAG, repro archives, external cache, bidirectional sync
- Source normalized to 1NF (#113): pipe-separated source → boolean from_* columns
- Teaching canon refactored (#114): single merge, build_teaching_canon simplified 363→100 lines
- Test infra (#117–#123, #129–#130): pytest-timeout, make check-fast
- Flags column normalized (#126): removed derived list from extended_works.csv; boolean columns are source of truth
- catalog_bibcnrs as DVC stage (#134): data/exports/ DVC-tracked
- Teaching source pipeline (#135): scraped syllabi → YAML → teaching_works.csv
- Teaching scraper improvement (#258): PDF table extraction + chunk overlap, manual catalog removed — scraper covers all 24 reference works alone
- Split discover into per-source DVC stages (#152): parallel, granular, skippable
- OpenAlex --from-date incremental filtering (#153): budget-aware, sidecar auto-detect
- Venue table replaces fig-seed (#150, #151): @tbl-venues in §3.4 body
- Companion paper complete draft (#149): all sections filled
- Retry robustness + budget guard (#171): unified retry_get, API key fix, budget-aware fetch
- Split embeddings (#189): enrich_embeddings.py (Phase 1 encoding) + analyze_embeddings.py (Phase 2 UMAP+clustering)
- Phase separation + manuscript cleanup (#189b): surgical Makefile deps, no API calls in Phase 3, structural break purge, layout fixes
- Enrichment pipeline independence (#428): 4 DVC stages + join_enrichments.py, post-checkout hook symlinks .dvc/config.local (#505)
- Code smell cleanup (#507): 26 dead imports removed, 11 complex functions refactored, global cache → class, normalize_doi_safe helper, exception narrowing
- God module split (#542): `analyze_genealogy.py` 808→322L, M/V architecture with table-as-contract, robustness to `analyze_cocitation.py`
- PDF opt-in flip (#544): `save_figure()` default from PDF-on to PDF-off across 33 files, `TestPdfDiscipline` guard (#545)
- Fuzzy ref matching (#539): GROBID-parsed citation refs matched to corpus works via rapidfuzz, new `ref_match` DVC stage, integrated into `corpus_merge_citations`
- Worktree isolation (#568): every conversation runs in throwaway worktree via `EnterWorktree`, `.worktreeinclude` replaces post-checkout symlinks
- Text normalization (#533): ftfy + html.unescape at merge funnel point, fixes ~3,000 rows with encoding artifacts from upstream aggregators
- GROBID citation parsing (#538): 352K unstructured Crossref refs → structured title/author/year via local GROBID (podman), 200 cit/sec, JSONL cache
- Crossref DOI fallback (#569): `enrich_dois` queries Crossref when OpenAlex has no DOI, 9,268 OA-only candidates unlocked
- 1-output-per-invocation (#594): `compute_breakpoints.py` refactored to 3 mutually exclusive modes, Makefile targets split from grouped `&:` to separate `--output $@` rules
