# Roadmap

## North star

Building toward a book on international climate finance between solidarity and profit. This repo is the research infrastructure: a 30K-work corpus, analysis pipeline, and the articles that test each piece of the argument before it becomes a chapter.

## Oeconomia manuscript next steps

Submitted to Oeconomia (Varia) on 2026-03-18. Waiting for referee reports (~3 months).

- [ ] Wait for reviewers feedback
- [ ] Revise and Resubmit
- [ ] Prepare ESHET-HES conference slides (Nice, May 26–29, 2026)
- [ ] Continue Tier 1 reading plan (defence against reviewer questions)

## Data paper manuscript next steps

Submitted data paper to RDJ4HSS (diamond OA).

- [ ] Wait for reviewers feedback
- [ ] Revise and Resubmit
- [ ] Present at conference

## Charles Gide conference (Vannes, July 2-4)

21st International Colloquium of the Charles Gide Association, theme "Crises". Abstract accepted.

- [ ] Write conference paper (due 2026-06-15)
- [ ] Present at Vannes (2026-07-02 to 04)
- [ ] Consider submission to RHPE special issue on "Crises" (call post-conference)

## Next articles

- [ ] **Companion methods paper** — How can embedding-based clustering reveal intellectual structure in a heterogeneous, policy-entangled scholarly field? Contribution: a replicable pipeline for mapping fields where bibliometric boundaries are contested. Journals: Quantitative Science Studies, Scientometrics.
- [ ] **OECD vs. Oxfam** — How do competing accounting frameworks produce divergent truths from the same financial flows? Contribution: a sociology-of-quantification case study showing how measurement conventions perform political positions on North-South climate debt. Requires document-to-evidence extraction capabilities (cf. [AEDIST](https://github.com/MinhHaDuong/aedist) stage 2). Journals: Accounting, Organizations and Society; Social Studies of Science.
- [ ] **MDB greening pivot** — How did multilateral development banks reframe existing portfolios as "climate finance" without changing what they fund? Contribution: an economization analysis of institutional relabeling as performative category work. Requires document-to-evidence extraction capabilities (cf. AEDIST stage 2). Journals: Review of International Political Economy, New Political Economy.
- [ ] **Carbon markets as failed performativity** — Why did the CDM fail to produce the efficient abatement market it modeled, and is Article 6 repeating the same design flaws? Contribution: a MacKenzie-style analysis of how market devices for North-South carbon transfers failed to perform the world they assumed. Journals: Economy and Society, Journal of Cultural Economy.
- [ ] **Sectoral deals vs. global targets** — Why are sector-by-sector technology cooperation agreements more effective than aggregate financial pledges? Contribution: a comparative policy analysis using the Montreal Protocol as benchmark, arguing the NCQG $300bn target repeats the $100bn's structural failure. Journals: Climate Policy, Global Environmental Politics.

## Milestones

- **Project start (2026-02-18)**: repo created, first commit, manuscript plan, corpus pipeline design
- **v1.0 — Oeconomia submission (2026-03-18)**: tag v1.0, corpus pipeline (6 sources, DVC, teaching scraper), analysis (embeddings, clustering, figures), manuscript (all sections, house style, AI-tell sweep), submission packaging (Zenodo, HAL, cover letter)
- **v1.1 — RDJ4HSS data paper (2026-03-26)**: tag v1.1, data paper drafted and submitted, companion paper outlined, reproducibility archives
- **v1.1.1 — Pipeline refactor (2026-03)**: enrichment split into 4 independent DVC stages (#428), code smell cleanup (#507), agent harness consolidation, script I/O discipline (#547, #549)
- **v1.1.2 — Citation enrichment (in progress)**: GROBID reference parsing (#539), Crossref DOI fallback, circuit breakers (#590, #598), citation hardening (#529)
- **Imperial Dragon harness (2026-04-01)**: workflow renamed from Dragon Dreaming (4 phases) to Imperial Dragon (5 claws), generic harness extracted to ~/.claude/ (#628)
