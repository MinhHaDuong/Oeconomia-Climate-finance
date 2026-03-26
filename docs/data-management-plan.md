# Plan de gestion des données / Data Management Plan

**Project**: A Curated Corpus of Climate Finance Literature, 1990–2024
**Author**: Minh Ha-Duong (ORCID 0000-0003-2398-9009)
**Affiliation**: CNRS, CIRED (UMR 8568 CNRS–ENPC–Cirad–AgroParisTech–EHESS)
**Date**: 2026-03-26
**Version**: 1.0

> Structured following the CNRS template on DMP OPIDoR (Science Europe model).
> Satisfies CNRS Plan pour la Science Ouverte, Loi République numérique (Art. 30),
> and Plan National pour la Science Ouverte requirements.

---

## 1. Data description and collection

### 1.1 What data does the project produce or reuse?

The project produces a **multilingual bibliometric corpus** of scholarship
around climate finance (1990–2024). Three categories of data:

| Dataset | Format | Size | Origin |
|---------|--------|------|--------|
| climate_finance_corpus.csv | CSV (UTF-8, RFC 4180) | 42,368 rows raw (31,204 after filtering) | Merged from 6 sources; deposit artifact via `prepare_deposit.py` |
| embeddings.npz | NumPy compressed archive | 37,928 × 1024 float32 | Computed (BGE-M3 sentence-transformer) |
| citations.csv | CSV | 929,014 rows total (797,975 refined) | Extracted via Crossref + OpenAlex |
| Per-source catalogs (×6) | CSV | Variable | API harvests + manual exports |
| Raw API responses | Gzipped JSONL | ~2 GB | OpenAlex, ISTEX, Crossref, World Bank |
| Pipeline source code | Python, YAML, Makefile | ~150 files | Original |

**Reused data**: OpenAlex metadata (CC0), ISTEX metadata (public API), Crossref
citation data (public API), World Bank documents API (public).

**Restricted-source data**: bibCNRS exports (requires CNRS Janus credentials),
SciSpace exports (commercial tool). Pre-harvested exports are included in the
deposit to ensure reproducibility.

### 1.2 What standards or methodologies will be applied?

- **Identifiers**: DOIs (normalised, lowercased), OpenAlex IDs, ISO 639-1 language codes
- **Metadata**: DataCite schema (via Zenodo), Dublin Core (via HAL)
- **File formats**: CSV (RFC 4180), NumPy NPZ, gzipped JSONL — all open, non-proprietary
- **Pipeline**: DVC (Data Version Control) DAG for reproducibility
- **Versioning**: Semantic versioning; `in_v1` column for backward compatibility

## 2. Documentation and data quality

### 2.1 What documentation accompanies the data?

- **Data paper** (submitted to RDJ4HSS): full methodology, data records, technical validation
- **Technical report** (`content/technical-report.qmd`): detailed pipeline documentation
- **README-datapaper.md**: two-level verification protocol (checksums + full rebuild)
- **Inline audit trail**: `is_flagged`, `flag_reason`, `is_protected` columns in corpus CSV
- **DVC pipeline definition** (`dvc.yaml`): complete dependency graph
- **Version-controlled configuration**: keyword taxonomy, quality thresholds, model parameters

### 2.2 What quality controls are applied?

1. **Six-flag filtering pipeline** with full audit trail:
   - Missing metadata, absent abstract + irrelevant title, title blacklist,
     citation isolation, semantic outlier, cross-encoder relevance scoring
2. **Protection criteria** override flags: citation count ≥50, multi-source presence,
   within-corpus citations, teaching syllabus appearance
3. **Cross-validation**: stratified sample of 30 papers, precision = 1.0, recall = 1.0
4. **Human validation**: 100 papers for relevance scoring calibration (AUC = 0.818)
5. **Checksum verification**: MD5 checksums for bitwise reproducibility checks
6. **Structural verification**: schema, row-count ±5%, statistical similarity on rebuild

## 3. Storage and backup during research

### 3.1 How is data stored and backed up during the project?

| Layer | Location | Backup frequency |
|-------|----------|-----------------|
| Working data | Local workstation (SSD) | Continuous (git + DVC) |
| Git repository | GitHub (private, MIT licence) | Every commit |
| DVC remote | Default DVC remote | Every `dvc push` |
| Raw API responses | Append-only pool/ directory | Archived, never overwritten |

- **Environment pinning**: `PYTHONHASHSEED=0`, `SOURCE_DATE_EPOCH=0`, dependencies
  locked in `pyproject.toml`
- **Git hooks** enforce: no commits on main, no secrets, no large files (>500 KB),
  no conflict markers

### 3.2 How is access managed during the project?

- GitHub repository: private during review, public upon acceptance
- `.env` file (gitignored): API keys, machine-specific paths, agent credentials
- CNRS Janus credentials: personal, not shared — pre-harvested exports included instead
- Machine user (`HDMX-coding-agent`): scoped GitHub PAT for CI/automation only

## 4. Legal and ethical requirements, codes of conduct

### 4.1 What legal issues apply to data management?

**Loi pour une République numérique (2016)**:
- Art. 30 (Code de la recherche L.533-4): the accepted manuscript may be deposited
  in open access after a 12-month embargo (SHS). This applies to the Oeconomia
  manuscript; this project deposits immediately (preprint on HAL).
- Art. 30 al. II: research data associated with a publication are freely reusable
  once made public. This is the primary legal basis for the corpus deposit.
  The corpus CSV is published under CC BY 4.0.
- Art. 38 (TDM exception): text and data mining for public research is authorised.
  This covers the API harvesting and NLP processing in the pipeline.

**Publisher redistribution restrictions**:
- **Abstracts are excluded** from the deposited CSV. Publisher terms prohibit bulk
  redistribution of abstract text. Users can retrieve abstracts via DOI lookup
  (OpenAlex API, Crossref API).
- Bibliographic metadata (title, author, year, DOI, venue) is factual data,
  not subject to copyright.

**Database sui generis right (EU Directive 96/9/EC)**:
- The corpus constitutes a new database created through substantial investment
  in collection, verification, and presentation. The sui generis right belongs
  to the author. CC BY 4.0 licensing explicitly grants reuse rights.

**bibCNRS terms of use**:
- bibCNRS aggregates licensed databases (Gale, Wanfang, NewsBank). Raw full-text
  is not redistributed. Only bibliographic metadata (title, author, year, source)
  is included in the deposit — factual data exempt from database protection.
- Pre-harvested exports are included for reproducibility; re-harvesting requires
  CNRS Janus institutional credentials.

**SciSpace**:
- Commercial tool exports contain bibliographic metadata only (no full text).
  Metadata is factual and redistributable. Exports are included for reproducibility.

### 4.2 Ethical issues

- The study uses only **publicly available bibliographic metadata**; no human
  subjects were involved (no IRB/CNIL declaration required).
- No personal data is processed. Author names are public bibliographic metadata.
- AI tools (sentence-transformers, cross-encoder reranker, LLM extraction) are
  used for data processing only; their use is documented in the data paper and
  technical report.

### 4.3 CNRS-specific obligations

- **HAL deposit**: mandatory for CNRS researchers. Done: hal-05558422v1
  (Oeconomia manuscript). The data paper will also be deposited on HAL.
- **CRAC dossier**: the Zenodo dataset is linked to the HAL deposit via
  "Ressource associée" metadata, enabling inclusion in annual activity report.
- **HAL licence**: mandatory from January 2026 for all full-text deposits.
  Applied: CC BY 4.0.
- **CNRS Plan pour la Science Ouverte**: this project is fully compliant —
  open access publication, open data deposit, open source code.

## 5. Data sharing and long-term preservation

### 5.1 How and when will data be shared?

| Dataset | Repository | Licence | Embargo | DOI |
|---------|-----------|---------|---------|-----|
| Corpus + embeddings + citations | Zenodo | CC BY 4.0 | None | 10.5281/zenodo.19097045 |
| Pipeline source code | GitHub | MIT | Until acceptance | — |
| Oeconomia manuscript | HAL | CC BY 4.0 | None (preprint) | hal-05558422v1 |
| Data paper | HAL + journal | CC BY 4.0 | None (diamond OA) | TBD |

**Versioning strategy**:
- Zenodo concept DOI (stable across versions): 10.5281/zenodo.19097045
- Version-specific DOIs minted automatically by Zenodo
- `in_v1` column in corpus CSV enables backward compatibility
- Git tags mark submission milestones (e.g., `v1.0-submission`)

**Timeline**:
1. ✅ v1.0 deposited on Zenodo (2026-03-18, with Oeconomia submission)
2. ✅ v1.1 ready (corpus refined, teaching canon expanded)
3. Pending: update Zenodo deposit to v1.1 (with data paper submission)
4. Pending: make GitHub repository public (upon Oeconomia acceptance or data paper submission)

### 5.2 How will data be preserved for the long term?

**Primary archive**: Zenodo (CERN-hosted, indefinite preservation commitment).
Files are stored in CERN's EOS storage infrastructure with geographic redundancy.

**Why Zenodo over Recherche Data Gouv?** CNRS recommends its institutional space
on Recherche Data Gouv as the primary data repository. However, Zenodo was chosen
for international visibility and because the dataset targets a global audience
(8 languages, 6 sources across institutional traditions). The Zenodo DOI is linked
from the HAL record via "Ressource associée" metadata, ensuring institutional
discoverability within the French open-science ecosystem. A pointer record on
Recherche Data Gouv may be added if required by CNRS evaluation.

**Secondary archives**:
- HAL (French national open-science archive, CCSD/CNRS, CoreTrustSeal since 2021) — manuscript and data paper
- GitHub (code) — not a preservation repository, but provides redundancy
- Software Heritage: pipeline code to be archived via `save code now` upon repository publication

**Format longevity**: all data files use plain-text, non-proprietary formats
(CSV, NPZ/NumPy, JSONL). No specialised software is required to read the data
beyond standard scientific Python libraries.

**Retention**: indefinite. Zenodo's preservation policy guarantees a minimum of
20 years. The dataset's value is historical — climate finance literature from
1990–2024 does not expire.

### 5.3 What resources are needed for data management?

| Item | Cost | Source |
|------|------|--------|
| Zenodo deposit | Free (up to 50 GB) | CERN/OpenAIRE |
| HAL deposit | Free | CCSD/CNRS |
| GitHub repository | Free (public) | Microsoft/GitHub |
| OpenAlex API | Free (Premium key donated) | OurResearch |
| Compute (embedding generation) | ~2h GPU time | Existing workstation (NVIDIA RTX A4000) |
| Data paper publication (RDJ4HSS) | Free (diamond OA) | No APC |
| Author time | Permanent position | CNRS |

No dedicated data management budget is required. All infrastructure costs are
covered by existing institutional resources. The data paper targets RDJ4HSS,
a diamond open-access journal with no author-facing charges.

## 6. Data management responsibilities

**Data controller**: Minh Ha-Duong (CNRS permanent researcher, CIRED)

**Responsibilities**:
- Corpus construction, quality control, and documentation: Minh Ha-Duong
- Zenodo deposit management and versioning: Minh Ha-Duong
- HAL deposit: Minh Ha-Duong
- Long-term maintenance: data is static (1990–2024 window); no ongoing
  curation required after deposit. Future corpus extensions would be new versions.

**Succession**: in the event the data controller is no longer available,
the Zenodo deposit persists independently (CERN infrastructure). The GitHub
repository can be transferred or forked. CIRED laboratory retains institutional
knowledge through the published data paper and technical report.

---

## Appendix: FAIR self-assessment

| Principle | Status | Evidence |
|-----------|--------|----------|
| **F1** Globally unique persistent identifier | ✅ | Zenodo DOI 10.5281/zenodo.19097045 |
| **F2** Rich metadata | ✅ | DataCite metadata on Zenodo, Dublin Core on HAL |
| **F3** Metadata includes data identifier | ✅ | DOI in all metadata records |
| **F4** Registered in searchable resource | ✅ | Zenodo, HAL, OpenAIRE, DataCite |
| **A1** Retrievable by standardised protocol | ✅ | HTTPS (Zenodo REST API, direct download) |
| **A2** Metadata accessible even if data unavailable | ✅ | Zenodo and HAL preserve metadata independently |
| **I1** Knowledge representation language | ✅ | CSV (RFC 4180), NumPy NPZ |
| **I2** FAIR vocabularies | ✅ | ISO 639-1 (languages), DOIs (identifiers), DataCite (metadata) |
| **I3** Qualified references | ✅ | DOI cross-references, `in_v1` version tracking |
| **R1** Plurality of attributes | ✅ | 20+ columns per work, full provenance flags |
| **R1.1** Clear licence | ✅ | CC BY 4.0 (data), MIT (code) |
| **R1.2** Provenance | ✅ | `from_*` boolean columns, audit trail, DVC pipeline |
| **R1.3** Domain-relevant standards | ✅ | Bibliometric conventions, Science Europe DMP model |

---

*This DMP follows the CNRS structured template (Science Europe model) and is
intended for registration on [DMP OPIDoR](https://dmp.opidor.fr/). It will be
updated upon data paper acceptance and repository publication.*
