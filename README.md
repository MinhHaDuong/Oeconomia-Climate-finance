# Climate Finance History — Œconomia Article Project

**Title:** Counting Climate Finance: How an Economic Object Was Made (1990–2025)

## Vision

This project analyzes the history of climate finance as an economic object, examining how economists and institutions (OECD DAC, UNFCCC, multilateral development banks) co-produced the categories, metrics, and accounting frameworks that made climate finance measurable and governable between 1990–2025.

It is intellectual history that uses climate finance as a case study for understanding how economists create governable objects through quantification.

## Rationale

Publishing a few articles to lay the groundwork for a book project described in `docs/projet livre - pitch.md`

## Documents

| Document | File | Target journal | Status |
|----------|------|----------------|--------|
| Manuscript | `content/manuscript.qmd` | Œconomia (Varia) | Draft, revising |
| Technical report | `content/technical-report.qmd` | HAL working paper | Complete |
| Data paper | `content/data-paper.qmd` | Scientific Data | Outline + reused sections |
| Companion paper | `content/companion-paper.qmd` | Scientometrics / QSS | Outline |

All four are Quarto documents sharing fragments via `{{< include >}}` from `content/_includes/`.

## Key themes

1. **Categorization:** How OECD DAC categories (grants/loans, bilateral/multilateral, Rio markers) structured climate finance
2. **Quantification:** Grant-equivalent methodology, face value debates, mobilized private finance accounting
3. **Controversies:** OECD vs. Oxfam methodologies, additionality, double counting
4. **Actors:** Economists as policy experts (Jan Corfee-Morlot, Nicholas Stern, HLPF 2010)
5. **Governance:** $100bn commitment → $300bn NCQG transition (Copenhagen to Baku)

## Theoretical framework

- **Sociology of quantification:** Desrosières (commensuration), Porter (trust in numbers)
- **Performativity:** Callon, MacKenzie (how metrics shape reality)
- **Economization:** Fourcade, Çalışkan
- **History of economic thought:** Development economics + environmental economics genealogy
- **STS:** Boundary work, infrastructures of knowledge

## Prerequisites

- **[Quarto](https://quarto.org/docs/get-started/)** (≥ 1.4) — document rendering
- **[TinyTeX](https://quarto.org/docs/output-formats/pdf-engine.html)** or full TeX Live with XeLaTeX — PDF output
- **[uv](https://docs.astral.sh/uv/)** — Python dependency management

## Repository structure

```
├── _quarto.yml                       # Quarto project config (4 documents)
├── content/                          # All Quarto source material
│   ├── manuscript.qmd                # Main article (Œconomia)
│   ├── technical-report.qmd          # Full pipeline documentation
│   ├── data-paper.qmd                # Corpus data paper
│   ├── companion-paper.qmd           # Methods companion
│   ├── _includes/                    # Shared Markdown fragments
│   ├── bibliography/                 # main.bib + oeconomia.csl
│   ├── figures/                      # Generated figures (gitignored)
│   └── tables/                       # Generated tables (gitignored)
├── output/                           # Quarto rendered output (gitignored)
├── CLAUDE.md                         # AI redirect → AGENTS.md
├── AGENTS.md                         # AI workflow orchestration
├── ROADMAP.md                        # Milestones and deliverables
├── STATE.md                          # Current decisions and blockers
├── Makefile                          # Build: make manuscript, make papers, make figures
├── data/                             # DVC-managed data (dvc pull to populate)
│   ├── catalogs/                    #   Corpus CSVs, embeddings, caches
│   └── pool/                        #   Raw API responses (gzipped JSONL)
├── scripts/                          # Python analysis pipeline
├── docs/                             # Guidelines, journal info, book project notes
├── release/                          # Releases outside CIRED. Append-only.
└── attic/                            # Old stuff to delete when paper is accepted
```

## Data

Corpus data (~1.3 GB) lives in `data/` and is version-controlled with
[DVC](https://dvc.org/). Git tracks `.dvc` pointer files (hashes); the actual
data is stored in the DVC remote on padme.

### Setup (first time after cloning)

```bash
cp .env.example .env                    # CLIMATE_FINANCE_DATA=data
uv sync                                 # Phase 2/3 deps only (no DVC)
uv sync --group corpus                  # add Phase 1 deps (DVC, torch, etc.)
uv run dvc pull                         # download data from padme remote
```

### Two-machine workflow (doudou ↔ padme)

DVC push/pull is **bidirectional**: whoever runs the pipeline pushes, everyone
else pulls. The remote (`padme:/data/projets/dvc/...`) is a content-addressed
store — no conflicts as long as `.dvc` pointers stay in sync via git.

```bash
# Run the corpus pipeline (on any machine — typically padme for GPU):
make corpus                              # runs dvc repro (slow, API calls)
uv run dvc push                          # upload results to shared store
git add dvc.lock data/catalogs/.gitignore
git commit -m "Corpus update" && git push

# On the other machine — sync and use:
git pull                                 # get updated .dvc pointers
uv run dvc pull                          # download the new data
make figures && make manuscript          # Phase 2 + 3 (no DVC needed)
```

### Dependency groups

| Group | Install command | Who needs it |
|-------|----------------|--------------|
| (default) | `uv sync` | Phase 2 (figures) and Phase 3 (manuscript) users |
| corpus | `uv sync --group corpus` | Phase 1 (corpus building): adds DVC, torch, sentence-transformers |

### DVC on padme (the remote host)

Since padme hosts the DVC remote, it uses a local path override to avoid SSH
loopback. Run once after cloning on padme:

```bash
uv run dvc remote modify --local padme url /data/projets/dvc/oeconomia-climate-finance
```

### Building documents

`content/figures/` and `content/tables/` are gitignored — they are 100% script-generated.
After pulling data, regenerate them before building documents:

```bash
make corpus-validate  # run acceptance tests on corpus
make figures          # regenerate all figures and tables (~2 min)
make manuscript       # build PDF (requires figures)
```

## Project documentation

| File | Purpose |
|------|---------|
| `AGENTS.md` | AI workflow orchestration, Dragon Dreaming phases, git discipline |
| `ROADMAP.md` | Milestones: what's done, what's next |
| `STATE.md` | Current snapshot: stats, blockers, priorities |
| `docs/writing-guidelines.md` | Manuscript prose style, language polish rules |
| `docs/coding-guidelines.md` | Pipeline phases, script reference, conventions |
| `docs/oeconomia-style.md` | Journal house style |

## Contact

- **Journal:** Œconomia – History / Methodology / Philosophy
  - https://journals.openedition.org/oeconomia/
  - http://journals.sfu.ca/oeconomia
