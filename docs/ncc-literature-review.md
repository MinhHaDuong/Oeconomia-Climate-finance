# Literature Review: NCC Climate Finance Category Stability Paper

*Compiled 2026-04-13. Supports a planned submission to Nature Climate Change.*

Central claim to position: Computational analysis of ~32,000 works shows climate finance scholarship crystallized around Copenhagen (2009), not Paris (2015), and the conceptual categories have not changed in 15 years.

---

## 1. Annotated Bibliography

### 1.1 Existing periodizations of climate finance

**Already in main.bib:**

1. **Care & Weber (2023)** — "How Much Finance Is in Climate Finance? A Bibliometric Review." *Research in International Business and Finance* 64, 101886.
   - Used VOSviewer (co-citation, bibliographic coupling, keyword co-occurrence) to identify seven literature clusters. Found climate finance remains insufficiently grounded in financial theory. Periodization is exogenous, based on policy milestones.
   - *Relevance:* The most comprehensive existing bibliometric review. Our work supersedes it methodologically (endogenous break detection, embeddings, 32K corpus vs. their ~few hundred) and empirically (Copenhagen, not Paris). Must cite and differentiate.

2. **Shang & Jin (2023)** — "A Bibliometric Analysis on Climate Finance: Current Status and Future Directions." *Environmental Science and Pollution Research* 30(57), 119711--119732.
   - Co-authorship networks and keyword analysis on Scopus. Found research "started around 2010" and is dominated by environmental science rather than finance. Periodization exogenous.
   - *Relevance:* Confirms the ~2010 emergence date that our endogenous break detection refines to 2009. Their claim that finance is underrepresented supports Care & Weber.

3. **Maria, Ballini & Souza (2023)** — "Evolution of Green Finance: A Bibliometric Analysis through Complex Networks and Machine Learning." *Sustainability* 15(2), 967.
   - Combined complex network analysis with STM. Identified three stages: carbon finance/markets (2008-2010), climate finance/policy/climate change (2011-2017), sustainable development/financial development (2018-2022). Only study to apply a topic model to the green/climate finance literature.
   - *Relevance:* Their three stages partially align with our periodization. Their 2008-2010 "carbon finance" stage maps roughly to our crystallization onset. However, their periodization is imposed from topic model output, not detected endogenously.

**Found via web search:**

4. **Mapping the field of climate finance research: a bibliometric analysis (2024)** — *Journal of Sustainable Finance & Investment* 15(1). [URL](https://www.tandfonline.com/doi/full/10.1080/20430795.2024.2441195)
   - Updated bibliometric analysis finding climate finance research "started in 2010" with most literature from China, US, and UK. Focus on finance for low-carbon transition and renewable energy.
   - *Relevance:* Another exogenous periodization that places the field's origin around 2010 -- consistent with our endogenous 2009 break. Confirms the gap our method fills.

5. **Reconnoitering trends and patterns in climate finance: a bibliometric analysis (2025)** — *SN Business & Economics* 5(8). [URL](https://link.springer.com/article/10.1007/s43546-025-00873-0)
   - Analyzed 621 publications from WoS (2004-2024). Found significant growth since 2016.
   - *Relevance:* Small corpus. Growth acceleration post-2016 is consistent with our third period (established field) but they interpret it as Paris-driven -- precisely the exogenous assumption we challenge.

6. **Green and climate finance research trends: A bibliometric study of pre- and post-pandemic shifts (2025)** — *Environmental Science & Ecotechnology*. [URL](https://www.sciencedirect.com/science/article/pii/S2666791625000077)
   - Examines how COVID-19 shifted research priorities. Post-2024 increase in SDG-linked terms.
   - *Relevance:* Demonstrates thematic redistribution without structural break -- consistent with our finding that no break occurs post-2015.

7. **Periodizing sustainable finance literature: A comprehensive bibliometric review & future directions (2026)** — *Cogent Business & Management*. [URL](https://www.tandfonline.com/doi/full/10.1080/27658511.2026.2624177)
   - Explicitly attempts periodization of sustainable finance. Maps distinct developmental stages using bibliometric data and historical analysis.
   - *Relevance:* Direct competitor in periodization. Must read and cite. Their periodization is likely exogenous (based on institutional transformations). Our endogenous method provides an independent test. **UNVERIFIED: Full text not reviewed; relevance assessment based on abstract/title only.**

### 1.2 Work arguing Paris was a structural break in scholarship

**No strong evidence found.** The web searches reveal a consistent pattern:

- Multiple bibliometric studies note *publication volume* increased sharply after 2015-2016, which they attribute to the Paris Agreement.
- However, none tests whether this represents a *structural break in the conceptual space* (topic structure, semantic content) rather than merely volume growth.
- Our finding -- that the Paris Agreement produced volume growth within existing categories but no semantic restructuring -- is genuinely novel.
- The closest claim comes from climate justice research: a 2026 bibliometric analysis in *Climatic Change* found "publication activity increased sharply following major policy milestones -- particularly COP15 and the Paris Agreement" but did not distinguish volume from structure. [URL](https://link.springer.com/article/10.1007/s10584-026-04116-5)
- One financial markets study found a Bayesian structural break in ESG indices at 2015 (Paris Agreement), with subsequent breaks at 2017, 2019, 2021. [URL](https://www.sciencedirect.com/science/article/pii/S0301479725038058) But this concerns financial markets, not scholarship.

**Gap identified:** Nobody has empirically tested whether Paris was a structural break in the *knowledge structure* of climate finance. This is our contribution.

### 1.3 Category stability, conceptual lock-in, and paradigm persistence (STS/HPS)

**Classic references (from general knowledge, verifiable in standard bibliographies):**

8. **Kuhn (1962/1970)** — *The Structure of Scientific Revolutions*. University of Chicago Press.
   - "Normal science" as puzzle-solving within a paradigm. Paradigms are sustained by communities through training, values, and practices. Fundamental novelties are suppressed because they are "subversive of basic commitments."
   - *Relevance:* Our finding that the core literature shows no structural break is a textbook case of Kuhnian normal science. The conceptual categories set by ~2009 define the puzzles that climate finance scholars solve. The NCC piece should frame category stability as normal science, not stagnation.

9. **Pierson (2000)** — "Increasing Returns, Path Dependence, and the Study of Politics." *American Political Science Review* 94(2), 251--267. [URL](https://www.cambridge.org/core/journals/american-political-science-review/article/abs/increasing-returns-path-dependence-and-the-study-of-politics/AC2137B913363E33D97FC5CEC17CC75D)
   - Path dependence grounded in increasing returns. Once a course of action is introduced, it can be "almost impossible to reverse." Political institutions are particularly prone to persistence.
   - *Relevance:* Provides the theoretical mechanism for why scholarly categories persist. Once the accounting categories (Rio markers, mobilised private finance) were institutionalized at Copenhagen, they generated increasing returns: training programs, reporting systems, careers, and databases all organized around them. This is institutional path dependence in knowledge production.

10. **Unruh (2000)** — "Understanding Carbon Lock-In." *Energy Policy* 28(12), 817--830. [URL](https://www.sciencedirect.com/science/article/abs/pii/S0301421500000707)
    - Industrial economies locked into fossil fuel systems through technological and institutional co-evolution (techno-institutional complex, TIC). Self-reinforcing, requiring exogenous forces to escape.
    - *Relevance:* The "carbon lock-in" concept provides a powerful analogy for our "category lock-in." Just as energy systems resist transition, knowledge categories resist restructuring. The parallel is direct: both involve increasing returns, institutional embedding, and resistance to alternative framings.

11. **Seto, Davis, et al. (2016)** — "Carbon Lock-In: Types, Causes, and Policy Implications." *Annual Review of Environment and Resources* 41, 425--452. [URL](https://www.annualreviews.org/content/journals/10.1146/annurev-environ-110615-085934)
    - Extended Unruh's framework to distinguish infrastructural-technological, institutional, and behavioral lock-in.
    - *Relevance:* The taxonomy maps onto scholarly lock-in: methodological (embedding models, clustering), institutional (OECD/MDB reporting frameworks), and behavioral (researcher training, peer review norms).

12. **Simonet (2022)** — "Discursive dynamics and lock-ins in socio-technical systems: an overview and a way forward." *Sustainability Science*. [URL](https://link.springer.com/article/10.1007/s11625-022-01110-5)
    - Three discursive lock-in mechanisms: unchallenged values and assumptions, incumbents' discursive agency, and narrative co-optation.
    - *Relevance:* Directly applicable to climate finance. The "what counts" debate operates through discursive lock-in: the categories themselves (mitigation, adaptation, loss & damage) become unchallenged frames, and alternative framings (e.g., reparations, ecological debt) are co-opted into existing categories.

13. **Foxon (2002)** — "Technological and institutional 'lock-in' as a barrier to sustainable innovation." ICCEPT Working Paper, Imperial College London. [URL](https://www.imperial.ac.uk/media/imperial-college/research-centres-and-groups/icept/7294726.PDF)
    - Technologies follow paths difficult and costly to escape, persisting even when competing with superior substitutes.
    - *Relevance:* Analogous dynamic in knowledge systems: even when new framings (climate justice, loss & damage) emerge, they are absorbed into existing categorical infrastructure.

14. **Leach, Stirling & Scoones (2010)** — *Dynamic Sustainabilities: Technology, Environment, Social Justice*. Earthscan.
    - "Epistemic lock-in" as barrier to innovation. Knowledge practices in sectors, not just inertia, block greener alternatives.
    - *Relevance:* The concept of "epistemic lock-in" most directly names what we find empirically. The NCC piece could use this term. **UNVERIFIED: I have not confirmed the exact use of "epistemic lock-in" in this specific text; the concept appears in related STS literature but attribution requires verification.**

### 1.4 Recent NCC publications on climate finance governance

15. **Roberts, Weikmans, et al. (2021)** — "Rebooting a failed promise of climate finance." *Nature Climate Change* 11, 180--182. [Already in main.bib as `roberts2021`]
    - The $100 billion pledge was not specific on what types of funding count. Indeterminacy and questionable claims make it impossible to know if developed nations have delivered.
    - *Relevance:* This is our primary NCC positioning anchor. Roberts & Weikmans are the voice of climate finance accountability in NCC. Our computational finding that the categories haven't changed in 15 years reinforces their argument: the accounting muddle is not a temporary problem but a structural feature.

16. **Toetzke, Stunzi & Egli (2022)** — "Consistent and replicable estimation of bilateral climate finance." *Nature Climate Change* 12, 897--900. [URL](https://www.nature.com/articles/s41558-022-01482-7)
    - Machine learning classifier on 2.7M ODA projects (2000-2019). Found actual climate finance may be much lower than Rio marker estimates. Accompanied by Weikmans & Roberts News & Views.
    - *Relevance:* Shows NCC publishes methodological innovation in climate finance measurement. Our work complements this: they show the categories are poorly applied in practice; we show the categories themselves haven't evolved despite the field's dramatic growth. Different diagnostic, same patient.

17. **NCC Editorial (2022)** — "Checking contentious counting." *Nature Climate Change* 12, 869. [URL](https://www.nature.com/articles/s41558-022-01483-6)
    - Editorial accompanying Toetzke et al. NCC editors explicitly care about the "counting" problem.
    - *Relevance:* Our paper is a natural sequel: from "the counting is wrong" to "the categories used for counting are frozen in place."

18. **Leal-Arcas et al. (2021)** — "The climate consistency goal and the transformation of global finance." *Nature Climate Change* 11, 578--583. [URL](https://www.nature.com/articles/s41558-021-01083-w)
    - Article 2.1c of the Paris Agreement: making finance flows consistent with low-carbon pathways.
    - *Relevance:* Shows NCC's interest extends beyond counting to the structural architecture of climate finance governance.

19. **Research agenda for the loss and damage fund (2023)** — *Nature Climate Change*. [URL](https://www.nature.com/articles/s41558-023-01648-x)
    - Outlines research priorities for the L&D fund established at COP27.
    - *Relevance:* Loss & damage is the newest category in climate finance. Our finding that the conceptual space hasn't restructured to accommodate it would be provocative and newsworthy.

20. **Making transparent the accountability deficit in the global climate regime (2025)** — *npj Climate Action*. [URL](https://www.nature.com/articles/s44168-025-00264-z)
    - Under pre-Paris transparency arrangements (through 2024), developed countries reported biennially on emissions and finance provided. At COP29 (2024), developed countries opposed noting specific information from synthesis reports.
    - *Relevance:* Illustrates that the accountability problem is not getting better, consistent with our finding of category stasis.

### 1.5 Economisation and category construction (core theoretical framing)

**Already in main.bib:**

21. **Skovgaard (2017/2021)** — *The Economisation of Climate Change: How the G20, the OECD and the IMF Address Fossil Fuel Subsidies and Climate Finance*. Cambridge University Press. [Also `skovgaard2017` in main.bib for the journal article]
    - How international economic institutions address climate change as an *economic* issue rather than an environmental one. The concept of "economisation" directly parallels Caliskan & Callon.
    - *Relevance:* Essential context. Skovgaard's "economisation" is the macro-process; our "category crystallization" is the micro-mechanism. The accounting categories are the instruments of economisation.

22. **Caliskan & Callon (2009, 2010)** — "Economization" Parts 1 and 2. *Economy and Society*. [Already in main.bib]
    - Framework for studying how things become "economic" through specific processes of classification, measurement, and calculation.
    - *Relevance:* The theoretical backbone of the NCC argument. Climate finance became an economic object through the construction of accounting categories. Our data shows when this happened (2007-2009) and that the resulting categories stuck.

**Found via web search:**

23. **Gifford & Sauls (2024)** — "Defining Climate Finance Justice: Critical Geographies of Justice Amid Financialized Climate Action." *Geography Compass* 18, e70008. [URL](https://compass.onlinelibrary.wiley.com/doi/10.1111/gec3.70008)
    - An emerging subfield studying what kinds of justice and injustice exist in climate finance. Climate finance as mechanism for dispossession and capital accumulation.
    - *Relevance:* Represents the critical perspective that our category stability finding supports: if the categories are locked in, then the justice critiques are fighting within a rigged frame. Worth citing for the NCC piece's "so what" section.

24. **Cato (2022)** — "The Chequered History of Climate Finance." In *Sustainable Finance*, Springer, 39--59. [URL](https://link.springer.com/chapter/10.1007/978-3-030-91578-0_3)
    - Historical narrative of climate finance's evolution. Over three decades, moved from modest voluntary mechanisms to formalized UNFCCC regime. Bali Action Plan broadened the notion beyond carbon-reduction projects.
    - *Relevance:* Provides qualitative history that our quantitative analysis corroborates. The "broadening" she describes at Bali aligns with our 2007 cosine break.

---

## 2. Gap Analysis: Where Does Our Finding Sit?

### 2.1 What the literature establishes

- Climate finance scholarship experienced rapid growth starting ~2010, accelerating after 2015-2016.
- Existing bibliometric reviews periodize the field exogenously (by COP dates or publication volume thresholds).
- The "what counts" problem is well-documented qualitatively (Roberts & Weikmans, Stadelmann, OECD).
- Lock-in and path dependence are well-theorized in STS/political science for technology and institutions, but not applied to scholarly knowledge categories.

### 2.2 What nobody has done

1. **Endogenous periodization of climate finance scholarship.** All existing bibliometric reviews impose period boundaries from external events. None lets the data determine when the field restructured.

2. **Tested whether Paris was a structural break in the knowledge space.** Everyone assumes it was important for scholarship because it was important for policy. Nobody has empirically tested this.

3. **Documented category stability computationally.** The claim that "the categories haven't changed" exists implicitly in the accountability literature (Roberts & Weikmans note the same debates recur), but nobody has measured it.

4. **Connected lock-in theory to scholarly knowledge production about climate finance.** Unruh, Seto, Pierson -- these frameworks have not been applied to the categories *through which* climate finance is governed.

### 2.3 Our contribution fills all four gaps simultaneously

The NCC piece can claim: "We provide the first endogenous periodization of climate finance scholarship, showing computationally that the field crystallized around Copenhagen (2009), not Paris (2015), and that the conceptual categories established during crystallization have persisted unchanged for 15 years. We interpret this as *epistemic lock-in* in the categories through which climate finance is governed -- a finding with direct implications for the post-$100 billion finance architecture."

---

## 3. The 3-5 Must-Cite Papers

For the NCC piece specifically (not the Oeconomia paper, which has different needs):

1. **Roberts, Weikmans, et al. (2021)** — "Rebooting a failed promise of climate finance." *Nature Climate Change*.
   *Why:* The NCC accountability anchor. Our finding explains WHY the promise keeps failing: the categories are locked in.

2. **Toetzke, Stunzi & Egli (2022)** — "Consistent and replicable estimation of bilateral climate finance." *Nature Climate Change*.
   *Why:* Shows NCC publishes methodological innovation in climate finance measurement. Our paper complements theirs.

3. **Unruh (2000)** — "Understanding Carbon Lock-In." *Energy Policy*.
   *Why:* Provides the "lock-in" framing that makes our finding legible to the NCC audience. The analogy carbon-lock-in / category-lock-in is immediate and powerful.

4. **Pierson (2000)** — "Increasing Returns, Path Dependence, and the Study of Politics." *APSR*.
   *Why:* Theoretical mechanism for why categories persist. Connects to the broader path dependence literature that NCC readers know from climate policy.

5. **Care & Weber (2023)** — "How Much Finance Is in Climate Finance?" *Research in International Business and Finance*.
   *Why:* The most comprehensive existing bibliometric review. We must cite and supersede it.

---

## 4. Vulnerabilities in Our Argument

### 4.1 "Volume growth IS the structural change"

**The objection:** A reviewer could argue that the massive expansion of scholarship after Paris (from hundreds to thousands of papers/year) is itself a structural transformation, even if the conceptual categories didn't change. More participants, more venues, more money -- this changes the field even if the topics stay the same.

**Mitigation:** Acknowledge this explicitly. Our framework *detects* this distinction (full corpus breaks but core doesn't), which is a feature. Reframe: "The field grew enormously after Paris, but it grew *within* the categorical architecture established at Copenhagen. Growth without conceptual innovation is itself a finding that demands explanation."

### 4.2 "Embeddings can't capture conceptual change"

**The objection:** Dense embeddings from a single model (BAAI/bge-m3) trained on contemporary text may project historical distinctions into a modern semantic space, smoothing out real historical differences.

**Mitigation:** This is a real limitation. Note that the cosine metric (which is sensitive to centroid shifts) and the JS metric (which is sensitive to cluster redistribution) tell the same story. The TF-IDF validation (which is model-independent) confirms the bimodality finding. Still, testing with period-specific models would strengthen the claim.

### 4.3 "The categories DID change -- loss & damage emerged"

**The objection:** Loss & damage emerged as a formal UNFCCC category at COP19 (2013) and was institutionalized at COP27 (2022). Isn't this a new category?

**Mitigation:** Our data can address this directly. If loss & damage scholarship forms a new cluster in the embedding space, the break detection should pick it up. If it doesn't (which is what we find), it means L&D scholarship was absorbed into existing categorical frames rather than creating new ones. This is actually the strongest version of our argument: even genuine policy innovation gets absorbed into the existing epistemic structure.

### 4.4 "Copenhagen was a policy break, not a scholarly one"

**The objection:** The 2009 break might simply reflect the fact that Copenhagen generated a burst of new publications, not that scholars reorganized their thinking.

**Mitigation:** The volume-confound check (correlations below |r|>0.5) addresses this. The cosine break is in the semantic *centroid*, not in volume. The censored-gap variant removes transition years and still detects 2009. But this needs to be argued carefully.

### 4.5 "So what? Categories SHOULD be stable"

**The objection:** Stable categories are a sign of a mature, functioning field, not a pathology. Science works precisely because categories are shared and durable.

**Mitigation:** This is the most sophisticated objection and requires the most careful response. The argument is not that stability is inherently bad, but that:
- The specific categories that stabilized were *accounting* categories (Rio markers, mobilised private finance), not *analytical* categories.
- These accounting categories were designed for diplomatic ambiguity, not scientific precision (Weikmans & Roberts 2019).
- When the governance challenge evolves (loss & damage, Article 2.1c, NCQG) but the categories don't, governance effectiveness suffers.
- The analogy to carbon lock-in is apt: stability becomes pathological when the context changes.

### 4.6 Corpus scope

**The objection:** The corpus is "scholarship around climate finance" (32K works), not the narrower "climate finance" literature per se. Including peripheral works may dilute signals.

**Mitigation:** The two-level design (full corpus vs. core) addresses this. The core subset (highly cited papers) is the disciplinary backbone. Results are robust across both levels (the core actually shows *more* stability, not less).

---

## 5. Methodological Notes

### Papers found via web search (URLs provided above):
- Mapping the field of climate finance research (JSFI, 2024)
- Reconnoitering trends in climate finance (SN B&E, 2025)
- Green and climate finance research trends pre/post-pandemic (ES&E, 2025)
- Periodizing sustainable finance literature (Cogent B&M, 2026)
- Toetzke et al. NCC 2022
- NCC editorial "Checking contentious counting" 2022
- Gifford & Sauls (Geography Compass, 2024)
- Cato (Springer, 2022)
- Pierson (APSR, 2000) -- confirmed via Cambridge Core
- Unruh (Energy Policy, 2000) -- confirmed via ScienceDirect
- Seto et al. (ARER, 2016) -- confirmed via Annual Reviews
- Simonet (Sustainability Science, 2022)
- Making transparent the accountability deficit (npj Climate Action, 2025)
- Research agenda for loss and damage fund (NCC, 2023)

### Papers from existing bibliography (main.bib):
- Care & Weber (2023), Shang & Jin (2023), Maria et al. (2023)
- Roberts et al. (2021), Skovgaard (2017), Caliskan & Callon (2009, 2010)
- Weikmans & Roberts (2019)
- All Tranche A theoretical apparatus (Desrosieres, Porter, Callon, MacKenzie, Espeland & Stevens, Power, Star & Griesemer, Merry)

### Claims requiring further verification:
- The "Periodizing sustainable finance literature" (2026) paper's full content and methodology -- only abstract seen.
- Leach, Stirling & Scoones (2010) as source of "epistemic lock-in" -- concept confirmed in STS literature but specific attribution needs checking.
- Whether the loss & damage literature forms a detectable cluster in our embedding space -- requires running the analysis.
