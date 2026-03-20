# Roadmap: Data paper publication

Target: Research Data Journal for the Humanities and Social Sciences (RDJ4HSS)
Format: Data paper, max 2,500 words, diamond OA

## Phase 0: Fix and verify (this week)

**Goal**: PR #251 is merge-ready, current corpus (v1.0) is accurately described.

| Task | Where | Time | Ticket |
|------|-------|------|--------|
| Regenerate Table 2 with correct Raw counts | Padme | 30 min | #252 |
| Verify Zenodo deposit has all 5 files + source catalogs | Doudou | 15 min | — |
| Author proofread of rendered PDF | — | 1 hour | — |
| Merge PR #251 to main | Doudou | 5 min | — |

**Exit**: Data paper accurately describes v1.0 corpus. Submittable as-is if we choose not to improve.

## Phase 1: Corpus expansion — new sources (next week)

**Goal**: Add 2 new automated, reproducible sources. Corpus becomes v1.1.

### 1a. Semantic Scholar (~2 hours on Padme)

- Uncomment 8 lines in `dvc.yaml`
- Set `S2_API_KEY` in `.env`
- Run: `dvc repro catalog_semanticscholar`
- Script exists and is tested. Expected yield: 500–2,000 unique works.
- Ticket #254 (updated scope)

### 1b. RePEc (multi-day on Padme)

**Step 1: Resync mirror** (1–2 days download)
```bash
rsync -avz --delete repec.org::RePEc /home/haduong/data/datasets/external/RePEc/
```
Current mirror is from 2013–2014. Climate finance literature exploded after 2015. Resync is essential.

**Step 2: Ingest into SQLite** (hours of processing)
The mirror has 1.15M ReDIF files totalling 108GB. Grepping for keywords is too slow. Ingest into a proper database:
- Parse all ReDIF files → SQLite table (handle, title, abstract, keywords, year, doi, file_url, journal)
- Index on title (FTS5), keywords, year
- Expected total: ~3–5M records (RePEc has ~4.4M items as of 2026)

**Step 3: Query for climate finance** (minutes)
- SQL queries with FTS5 matching the four-tier keyword taxonomy
- Export to `repec_works.csv` in standard catalog format
- Add `from_repec` column to merge pipeline

**Step 4: Integrate**
- New DVC stage `catalog_repec`
- Update `catalog_merge.py` source priority (after openalex, before istex)
- Expected yield: 1,000–5,000 unique works (working papers, policy briefs, NBER/CEPR/IZA series)

Ticket: new (create)

### Phase 1 exit

- Corpus v1.1: 7 or 8 sources (current 6 + S2 + RePEc)
- Rerun `compute_vars.py` → all `{{< meta >}}` variables update automatically
- Update data paper text: source count, Table 1 (add rows), Table 2 (regenerate)
- New Zenodo deposit (v1.1, same concept DOI)

## Phase 2: Corpus enrichment (1–2 weeks, Padme overnight)

**Goal**: Fill metadata gaps using full-text-first strategy. Corpus stays v1.1.

| Task | Population | Expected yield | Runtime | Priority |
|------|-----------|---------------|---------|----------|
| DOI pilot for 101 core works | 101 DOI-less, cited≥50 | 5–10 DOIs | 2 min | High |
| Full DOI sweep (OA-only, incl. RePEc handles) | ~8,000 | ~400–600 DOIs | 3 hours | Medium |
| URL enrichment (Unpaywall, CORE, web search) | DOI-less works | direct-access URLs | Overnight | Medium |
| GROBID abstract extraction from OA PDFs | URL-bearing, abstract-less | hundreds | Multi-night | Medium |
| LLM reference extraction from full text | URL-bearing, ref-less | hundreds | Multi-night | Low |
| OAI identifier resolution | Works with oai: handles | persistent IDs | Hours | Low |

### Identifier strategy

The pipeline should support multiple identifier types, not just DOIs:
- DOI (primary)
- RePEc handle (`RePEc:nbr:nberwo:12345`)
- OAI identifier (`oai:repec:...`)
- Direct URL (for grey literature, preprints)

Report %identified (DOI or handle or URL) instead of just %DOI.

### Phase 2 exit

- Metadata gaps reduced (target: 80%+ DOI/handle, 90%+ abstract)
- All enrichment scripts are idempotent and cached (re-runnable)
- Update Table 2 with improved metrics
- Recompute vars, rebuild data paper

## Phase 3: Audit and verify (1 week)

**Goal**: Independent quality check on the v1.1 corpus.

| Task | Where | Time | Ticket |
|------|-------|------|--------|
| LLM audit with qwen3.5:27b (local, 100-paper sample) | Padme | Overnight | #253 |
| Update data paper section 2.3 with audit results | Doudou | 30 min | — |
| Run `make check` (full test suite) | Padme | 10 min | — |
| Run `make corpus-validate` (acceptance checks) | Padme | 5 min | — |
| Verify repro archive: `make archive-datapaper` | Padme | 30 min | — |
| Build + checksum data paper PDF | Doudou | 5 min | — |

### Phase 3 exit

- Corpus v1.1 passes all acceptance tests
- LLM audit results reported in paper
- Repro archive builds and Level 1 verification passes
- Data paper PDF renders cleanly

## Phase 4: Submit (target: early April 2026)

| Task | When |
|------|------|
| Zenodo v1.1 deposit (upload new files, keep concept DOI) | Day 1 |
| Final proofread of data paper | Day 1 |
| Submit to RDJ4HSS via openjournals.nl | Day 1 |
| Update STATE.md and ROADMAP.md | Day 1 |

## Post-submission improvements (v1.2+)

- Full GROBID pipeline for all OA PDFs (abstract + reference extraction)
- LLM-generated abstracts for works with only titles
- Cross-lingual embedding model upgrade (if better multilingual models emerge)
- Conference presentation extraction (from slides, videos)
- Annual corpus refresh (append-only, year bounds extended)

## Dependencies and risks

| Risk | Mitigation |
|------|-----------|
| RePEc resync takes too long (TB of data?) | Check mirror size first; consider partial sync (economics archives only) |
| S2 API rate limits slow harvest | Use API key (10 req/s); overnight is fine |
| GROBID quality on non-English PDFs | Validate on 50-paper sample before full run |
| qwen3.5:27b OOMs on A4000 | Fall back to qwen3.5:9b |
| Zenodo deposit update breaks concept DOI | Test with sandbox.zenodo.org first |
