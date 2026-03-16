# Submission Plan

## 1. Cover Letter to Oeconomia

**To:** Francesco Sergi, Managing Editor, Oeconomia
**From:** Minh Ha-Duong, CIRED/CNRS
**Re:** Varia submission — "Counting Climate Finance. How Economists Made a Governable Object (1990–2025)"

---

Dear Professor Sergi,

Following your encouraging response of February 16, 2026 to my extended abstract submitted for the special issue on "History of Climate Economics," I am pleased to submit the full manuscript as a Varia contribution.

The paper traces how economists working in international organisations — particularly at the OECD Development Assistance Committee — constructed climate finance as a distinct economic object between 1990 and 2025. It argues that they did not discover a pre-existing reality but built the accounting categories (Rio markers, mobilised-private-finance methodologies, concessionality thresholds) through which climate-related financial flows were rendered measurable and governable. Drawing on the sociology of quantification (Desrosières, Porter), performativity (Callon, MacKenzie), and economization (Çalışkan and Callon), the paper situates this construction within the broader history of climate economics.

The historical argument is grounded in a computational analysis of approximately 27,500 works (1990–2025) from six bibliographic sources. Sentence-transformer embeddings and sliding-window divergence tests detect structural breaks endogenously, identifying a crystallisation between 2007 and 2014 and confirming that neither Paris (2015) nor Glasgow (2021) disrupted the field's conceptual architecture. The corpus analysis supports the historical interpretation; the periodisation is grounded in the institutional record.

The manuscript is approximately 9,600 words with 61 bibliographic references, 3 figures, and 2 tables. A full replication archive (data, code, and technical report) is available at [Zenodo DOI] and the technical report documenting the data pipeline is deposited as a CIRED working paper [HAL ID]. Source code is maintained at https://github.com/MinhHaDuong/Oeconomia-Climate-finance.

The paper is not under consideration elsewhere. A version of the abstract has been accepted for presentation at the ESHET-HES Joint Conference (Nice, May 2026).

I would be happy to provide any additional information needed for the evaluation process.

Respectfully,

Minh Ha-Duong
CIRED (Centre International de Recherche sur l'Environnement et le Développement)
CNRS / ENPC / AgroParisTech
minh.ha-duong@cnrs.fr

---

## 1b. DOI Strategy — Citable Companions

The manuscript currently cites a GitHub repository. Before submission, three companion objects need DOIs so the manuscript can reference stable, peer-legible records.

| Object | Where | DOI type | What it contains | Cite in manuscript as |
|--------|-------|----------|------------------|-----------------------|
| **Replication archive** | Zenodo | Dataset DOI | Code, data (refined_works.csv, embeddings.npz, etc.), figures, pyproject.toml, uv.lock — built by `make archive-manuscript` | "Data and code availability" paragraph |
| **Technical report** | HAL | Working paper | Full pipeline documentation (10 sections): corpus construction, embeddings, break detection, bimodality, reproducibility | Cited in-text where computational methods are described |
| **Manuscript preprint** (optional) | HAL or SocArXiv | Preprint DOI | The paper itself | Not cited in manuscript, but useful for conference slides and visibility |

### Workflow

1. **Tag the repo** `v1.0-submission` and push tag
2. **Create Zenodo archive:**
   - Link GitHub repo to Zenodo (one-time setup via zenodo.org/account/settings/github/)
   - Zenodo auto-creates a release archive from the tag
   - Or: upload `climate-finance-manuscript.tar.gz` (from `make archive-manuscript`) manually to Zenodo
   - Fill metadata: title, author, license (CC-BY-NC to match Oeconomia), description
   - Get DOI (e.g., `10.5281/zenodo.XXXXXXX`)
3. **Upload technical report to HAL:**
   - Build PDF: `quarto render technical-report.qmd --to pdf`
   - Deposit on HAL as "Document de travail" / working paper
   - Affiliation: CIRED (UMR 8568)
   - Get HAL ID (e.g., `hal-XXXXXXXX`)
4. **Update manuscript** `Data and code availability` paragraph:

   > **Data and code availability.** The corpus (27,494 works), analysis scripts, and reproducible pipeline are archived at [Zenodo DOI]. The technical report documenting data collection, processing, and analysis procedures is available as a CIRED working paper [HAL ID]. Source code is maintained at https://github.com/MinhHaDuong/Oeconomia-Climate-finance.

5. **Update bibliography** — add `technical-report` as a `@techreport` entry in `main.bib` so it can be cited in-text (e.g., in the corpus method paragraph of the introduction)

### Why this matters
- Reviewers and editors can verify computational claims without navigating GitHub
- Zenodo DOI is a permanent record even if the GitHub repo changes
- HAL deposit satisfies CNRS open-science requirements
- The technical report is the "minimum credible home" for the breakpoint analysis evidence that the manuscript cites but cannot fully present (PLAN.md §4)

---

## 1c. Use of AI Disclosure

Oeconomia's ethics code (COPE-based) has no specific AI policy yet. But proactive disclosure is both ethically correct and strategically wise — if a reviewer detects AI traces and you didn't disclose, credibility is destroyed. If you disclosed upfront, the same traces are a non-issue.

### Disclosure letter (to accompany submission)

---

**Disclosure: Use of AI Writing Assistance**

This manuscript was written with the assistance of large language models (Claude, Anthropic). The author used AI tools in the following capacities:

1. **Computational pipeline:** AI-assisted development of Python scripts for corpus construction, embedding analysis, structural break detection, and figure generation. All scripts were reviewed, tested, and validated by the author. The full pipeline is reproducible (`make figures` regenerates all outputs from data).

2. **Literature search and synthesis:** AI tools were used to search bibliographic databases, identify relevant works, and draft initial summaries. All cited works were read by the author; all claims were verified against primary sources.

3. **Drafting and revision:** AI tools produced draft text that the author substantively revised, restructured, and rewrote. The historical argument, periodisation, theoretical framework, and all interpretive claims are the author's own. Specific measures were taken to eliminate AI-characteristic language patterns (see project file `AGENTS.md` for the editorial protocol).

4. **Code review and project management:** AI tools assisted with code quality, build system design, and replication archive packaging.

The author takes sole responsibility for the content, arguments, and any errors in the manuscript. AI tools are not listed as co-authors, consistent with current COPE guidelines (AI tools cannot meet authorship criteria of accountability and consent).

Minh Ha-Duong

---

### Why disclose proactively

- **Oeconomia's readership** is HET scholars who study how knowledge is produced. They will be attuned to questions of authorship and epistemic integrity. Disclosure shows you take those questions seriously — it's performing the very reflexivity the paper advocates.
- **The manuscript itself argues** that economists built categories through institutional practices. Disclosing your own knowledge-production practices is consistent with the paper's theoretical commitments.
- **The AGENTS.md file** in your repo already documents the AI editorial protocol (blacklisted words, contrast farming limits, em-dash density targets). If anyone inspects the GitHub repo, they'll see it. Better to frame it yourself than let a reviewer discover it.
- **CNRS policy** (as of 2025) recommends transparency about AI use in research without prohibiting it.

### What NOT to say
- Don't apologise or be defensive
- Don't say "AI wrote the paper" — you wrote it with AI assistance
- Don't list the AI as co-author
- Don't hide it in a footnote — make it a separate disclosure document

---

## 2. Reading Plan (Defence Against "Vibewriting")

The manuscript cites 61 works. You need to demonstrate genuine familiarity with each, not just abstract-level knowledge. The risk areas are:

### Tier 1 — Must read cover-to-cover (or key chapters)
These are the theoretical backbone. A reviewer could quiz you on any of these.

| Work | Why | Time estimate |
|------|-----|---------------|
| Desrosieres 1998, *The Politics of Large Numbers* | Core theoretical framework (commensuration, statistical conventions) | 2 days |
| Porter 1995, *Trust in Numbers* | Quantification as governance | 1 day |
| Callon 1998, *Laws of the Markets* | Performativity — your §4.2 rests on this | 1 day |
| MacKenzie 2006, *An Engine, Not a Camera* | Performativity in finance | 1 day |
| Caliskan & Callon 2009, 2010 | Economization — your §4.3 | 2 hours (articles) |
| Espeland & Stevens 1998 | Commensuration — explicitly cited in intro | 1 hour (article) |
| Pottier 2016, *Le climat, a quel prix ?* | HET of climate economics — your lit review positions against this | 1 day |
| Stern 2007, *Stern Review* | At least the executive summary + ch. 1-2 | 3 hours |
| Aykut & Dahan 2015 | Co-production of climate science and governance | 1 day |

### Tier 2 — Must read the article carefully
These are cited for specific empirical claims. You need to know their methods and findings.

| Work | What you cite it for |
|------|---------------------|
| Roberts & Weikmans 2017 | Accounting disputes as distributive conflicts |
| Michaelowa 2007 | Incentive-driven over-reporting of Rio markers |
| Skovgaard 2017 | Finance ministries framing climate finance as ODA subset |
| Stadelmann et al. 2011 | Eight baseline options for additionality |
| Corfee-Morlot et al. 2009, 2012 | OECD statistical infrastructure — named actor in your narrative |
| Buchner et al. 2011, 2013 | CPI Global Landscape reports |
| Caruso & Ellis 2013; Jachnik 2015 | Mobilised private finance methodology |
| Hourcade 2015 | Financial paradox — named actor in your narrative |
| Kaul 2003, 2017 | Global public goods financing logic |
| Pauw 2022 | Post-2025 target governance |
| Monasterolo 2020 | Climate risk for financial regulators |
| Carty & Lecomte 2018; Zagema 2023 | Oxfam Shadow Reports |

### Tier 3 — Know the argument, skim the rest
Foundational references where you cite a specific point.

| Work | Your citation point |
|------|-------------------|
| Ayres & Kneese 1969 | Materials balance approach |
| Nordhaus 1992; Manne & Richels 1992 | IAMs as intertemporal optimisation |
| Weitzman 2007, 2009 | Discount rate debate with Stern |
| Negishi 1960 | Welfare weights in burden-sharing |
| Gieryn 1983 | Boundary work |
| Power 1997 | Audit society |
| Fourcade 2007 | Economization |
| Dahan 2010 | Models as boundary objects |

### Practical schedule
- **Week 1:** Tier 1 books (Desrosieres, Porter, Callon, MacKenzie, Pottier, Aykut & Dahan)
- **Week 2:** Tier 2 articles (Roberts & Weikmans, Michaelowa, Stadelmann, Corfee-Morlot, Skovgaard)
- **Week 3:** Remaining Tier 2 + all Tier 3 (skim)
- **Week 4:** Re-read manuscript with fresh eyes, annotate each citation with a margin note proving you can discuss it

### What to prepare for each cited work
For every reference, be able to answer in your own words:
1. What is the main argument?
2. What evidence/method do they use?
3. Why do I cite it at this specific point in my paper?
4. What would I say if a reviewer asked "but X argues the opposite"?

### Red flags to address
- You cite Desrosieres, Callon, MacKenzie as your theoretical framework. If a reviewer asks "how does your use of performativity differ from MacKenzie's original formulation?", you need a crisp answer.
- You name Corfee-Morlot and Hourcade as actors. Be ready to discuss their work beyond what the paper says.
- The "no structural break at Paris" finding is provocative. Be ready to defend it with knowledge of the post-2015 literature (Pauw, the ETF negotiations).

---

## 3. Internal Validation Plan

### 3A. LLM validation (2 models)

**Goal:** Catch logical gaps, unsupported claims, style issues, and AI-tell residue before human reviewers see it.

**Model 1 — Claude (Opus)**
Prompt: "You are an expert reviewer for Oeconomia, a journal in the history of economic thought. Review this manuscript for: (a) logical coherence of the three-act argument, (b) whether the computational evidence supports or merely illustrates the historical claims, (c) any claims that lack adequate citation, (d) passages that read as AI-generated (generic phrasing, empty hedging, decorative contrasts). Be specific and cite paragraph numbers."

**Model 2 — GPT-4 or Gemini**
Prompt: "You are a specialist in STS and the sociology of quantification. Review this manuscript for: (a) whether the theoretical framework (commensuration, performativity, economization) is applied correctly and distinctively, (b) whether the paper adds to or merely restates Desrosieres/Callon/MacKenzie, (c) potential objections a hostile reviewer might raise, (d) the balance between historical narrative and computational evidence. Be direct and critical."

**Process:**
1. Feed the rendered manuscript (not the markdown) to each model
2. Collect reviews independently
3. Cross-reference: issues flagged by both models are high-priority fixes
4. Address all issues before human review

### 3B. CIRED colleague validation (2 reviewers)

**Reviewer 1 — Climate economics expert**
Suggested profiles (pick one):
- **Jean-Charles Hourcade** — Named in the paper; his feedback would be authoritative but potentially conflicted. Better as informal conversation than formal review.
- **Franck Lecocq** — CIRED director, climate policy expertise, knows the OECD/UNFCCC landscape
- **Julie Rozenberg** — World Bank economist, practical climate finance knowledge

Ask them to review for:
- Factual accuracy of the institutional history (especially OECD/DAC, CDM, NCQG)
- Whether named actors and their roles are fairly represented
- Missing references that a climate economist would expect
- Whether the "no break at Paris" claim is defensible

**Reviewer 2 — History of economic thought / STS specialist**
Suggested profiles (pick one):
- **Antoine Missemer** — CNRS/CIRED, co-editor of the Oeconomia special issue, knows the journal's expectations intimately (but may be conflicted given the special issue decision)
- **Antonin Pottier** — Cited in the paper; HET of climate economics
- **Someone from the Oeconomia editorial board** — informal pre-review

Ask them to review for:
- Whether the paper meets Oeconomia's HET standards
- Whether the theoretical framework is well-integrated or bolted-on
- Whether the computational evidence is persuasive or distracting for the journal's readership
- Style and tone appropriate for the journal

**Process:**
1. Run LLM reviews first, fix issues
2. Send clean version to CIRED colleagues with a 2-week deadline
3. Provide them with: manuscript PDF, cover letter draft, and the specific questions above
4. Revise based on their feedback
5. Final `make clean && make all` + visual check
6. Submit

**Timeline:**
- Submit to Œconomia before ESHET-HES conference (Nice, May 26–29, 2026)
- Conference presentation serves as trial run; feedback informs R&R if needed

---

## 4. ESHET-HES Joint Conference (Nice, May 26-29, 2026)

### Status
- Abstract submitted January 15, 2026: "Economists Under Pressure: The Making of Climate Finance as an Economic Object (1990–2025)"
- **Accepted** (mission folder: `~/CNRS/missions/actif/2026-05-26:29 Nice ESHET-HES (accepté)/`)
- Conference theme: "Economists under Pressure and the Political Limits to Economics" — your paper fits perfectly

### Presentation plan

**Format:** Likely 20-25 min presentation + 10 min discussion (standard ESHET format)

**Slides structure (15-18 slides):**
1. Title + puzzle (the $100bn/$300bn that nobody can define)
2. Research question: how did economists make climate finance countable?
3. Theoretical toolkit: commensuration, performativity, economization
4. Method: 27,500 works, embedding-based break detection (keep brief)
5. **Act 1** — Before climate finance: three disconnected traditions (1 slide)
6. **Act 2** — The Copenhagen moment + OECD infrastructure (2-3 slides)
   - Rio markers, the AGF, Stern/Hourcade/Corfee-Morlot as architects
   - Fig 1: emergence graph (visual punch)
7. **Act 2** — The efficiency/accountability divide (1-2 slides)
   - Four controversies (loans, markers, mobilised finance, additionality)
8. **Act 3** — No break at Paris (1 slide, provocative)
   - The $100bn claim, the Oxfam counter-expertise
   - Fig 2: alluvial diagram showing stability
9. Theoretical synthesis: how the object was made governable (2 slides)
10. The constitutive tension: why bimodality is productive, not pathological
11. Conclusion + limitations + further research
12. Backup: corpus method details, breakpoint statistics

**Key messages for the HET audience:**
- This is NOT a bibliometric paper; it's intellectual history that *uses* computation
- The contribution is to the HET of climate economics (positioning against Pottier 2016, Aykut & Dahan 2015)
- The "economists under pressure" theme: economists at OECD/UNFCCC were under political pressure to make the $100bn countable — they responded by building accounting infrastructure that shaped reality

**Anticipated questions:**
- "How does this relate to the special issue?" — It was submitted but not selected for the special issue; this is an independent presentation of the same research
- "Isn't this just scientometrics?" — No, the computational analysis is corroborative; the argument is grounded in primary sources and institutional history
- "What about the Global South perspective?" — Acknowledged as a limitation; the paper traces the OECD-centric construction precisely to show its political character
- "How does your use of 'performativity' differ from MacKenzie?" — MacKenzie studied financial models that shaped markets; we study accounting categories that shaped an intergovernmental object. The mechanism is institutional (DAC reporting) rather than market-based.

### Logistics
- Book travel/hotel for Nice, May 25-29 (arrive day before)
- Prepare slides by mid-May
- The conference is a good venue to get informal feedback before the Oeconomia review process
- Consider: submit the Oeconomia paper *before* the conference (late April), so you can mention "under review at Oeconomia" in your presentation

### Synergy: Conference before or after submission?

**Option A — Submit before conference (recommended)**
- Submit to Oeconomia in late April
- Present at ESHET-HES in late May
- Conference feedback can inform revisions if Oeconomia requests R&R
- Cover letter can say "presented at ESHET-HES 2026"

**Option B — Submit after conference**
- Present at ESHET-HES, collect feedback
- Revise, then submit in June
- Risk: Sergi said "at your earliest convenience" — 4 months after encouragement is a long wait

**Recommendation: Option A.** Submit in late April. The conference presentation will be a trial run, and any feedback can be folded into revisions.
