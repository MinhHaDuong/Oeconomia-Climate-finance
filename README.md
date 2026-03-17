# Climate Finance History — Œconomia Article Project

**Title:** Counting Climate Finance: How an Economic Object Was Made (1990–2024)

## Vision

This project analyzes the history of climate finance as an economic object, examining how economists and institutions (OECD DAC, UNFCCC, multilateral development banks) co-produced the categories, metrics, and accounting frameworks that made climate finance measurable and governable between 1990–2024.

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
├── config/                           # Pipeline parameters (YAML)
├── Makefile                          # Build: make manuscript, make figures, make corpus
├── dvc.yaml                          # Phase 1 pipeline DAG (DVC stages)
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
uv sync                                 # Phase 2/3 deps only
uv sync --group corpus --extra cpu       # add Phase 1 deps (CPU torch)
uv sync --group corpus --extra cu130     # ...or CUDA 13 torch on GPU machines
uv run dvc cache dir /path/to/dvc-cache  # store blobs outside sync/backup dirs
uv run dvc pull                          # download data (~1.3 GB) from padme
```

The DVC cache directory should be outside Nextcloud-synced or snapshotted directories.
Example paths: `/home/user/data/projets/Oeconomia-Climate-finance/dvc-cache` (doudou),
`/data/projets/dvc-cache/oeconomia` (padme).

### Two-machine workflow (padme → doudou)

**Padme is the data authority.** The corpus pipeline runs on padme (GPU,
fast network to APIs). Doudou only pulls data — never pushes.

```bash
# On padme — run the corpus pipeline and push:
make corpus                              # runs dvc repro (slow, API calls)
uv run dvc push                          # upload results to shared store
git add dvc.lock && git commit -m "data: update dvc.lock" && git push

# On doudou — sync and use:
git pull                                 # get updated .dvc pointers
uv run dvc pull                          # download the new data
make figures && make manuscript          # Phase 2 + 3 (no DVC needed)
```

### Dependency groups

| Group | Install command | Who needs it |
|-------|----------------|--------------|
| (default) | `uv sync` | Phase 2 (figures) and Phase 3 (manuscript) users |
| corpus + cpu | `uv sync --group corpus --extra cpu` | Phase 1 on doudou (no GPU) |
| corpus + cu130 | `uv sync --group corpus --extra cu130` | Phase 1 on padme (CUDA 13.0 GPU) |

### DVC on padme (the remote host)

Since padme hosts the DVC remote, run these once after cloning:

```bash
uv run dvc remote modify --local padme url /data/projets/dvc/oeconomia-climate-finance
uv run dvc cache dir /data/projets/dvc-cache/oeconomia
```

The remote override avoids SSH loopback (padme accessing itself). Both
settings are stored in `.dvc/config.local` (gitignored, machine-specific).

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
| `STATE.md` | Current snapshot: stats, blockers, active PRs |
| `docs/writing-guidelines.md` | Manuscript prose style, language polish rules |
| `docs/coding-guidelines.md` | Pipeline phases, script reference, conventions |
| `docs/oeconomia-style.md` | Journal house style |

## Contact

minh.ha-duong@cnrs.fr
