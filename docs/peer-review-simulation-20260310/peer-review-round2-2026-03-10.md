# Simulated Peer Review — Round 2 Referee Reports

**Manuscript:** "Counting Climate Finance. How Economists Made a Governable Object (1990–2025)"
**Target journal:** *Œconomia — History / Methodology / Philosophy*
**Date:** 2026-03-10
**Method:** Three simulated reviewers (Claude Opus agents), reviewing the revised manuscript

**Verdict: All three reviewers recommend MINOR REVISION.**

---

## Reviewer 1 — History of Economic Thought

**REFEREE REPORT -- Round 2**

**Reviewer 1 (History of Economic Thought)**

**Manuscript:** "Counting Climate Finance. How Economists Made a Governable Object (1990--2025)"

**Journal:** *OEconomia -- History / Methodology / Philosophy*

---

**I. Status of Round 1 Concerns**

**Concern 1 -- Thin prosopography of "economists as architects": UNRESOLVED**

The author explicitly defers this concern, stating that archival work is "beyond the scope of this revision." I accept that a full prosopography involving institutional archives, interviews, and primary documents would constitute a separate project. However, I note that the manuscript does now do more with the figures it already names. The passages on Corfee-Morlot (Section 2.2), the Jachnik-Caruso Research Collaborative (Section 2.3), and the AGF composition including Stern and Hourcade (Section 2.4) provide a richer picture of how individual economists occupied specific institutional positions. This is not a prosopography, but it is a more satisfying account of situated agency than the first draft offered. I no longer regard this as a barrier to publication, provided the author adds a sentence in the limitations paragraph explicitly flagging the absence of archival and interview-based evidence as a constraint on claims about individual motivation and influence. The current limitations paragraph (final section) gestures at this but could be more direct.

**Concern 2 -- Theoretical framework layered on, not integrated: RESOLVED**

This was my principal structural objection, and the revision addresses it effectively. Commensuration now enters at Section 1.2 through Desrosieres, performativity at Section 2.1 through Callon, economization at Section 2.2 through Caliskan and Callon, and boundary work at Section 3.2 through Gieryn. Each concept is introduced at the moment in the narrative where it does explanatory work, not retroactively. Section 4 now reads as a synthetic recapitulation rather than a first exposition, and its reduced length (approximately 800 words) is proportionate to that function. The opening paragraph of Section 4 explicitly cross-references the earlier inline introductions. The revision also distinguishes Callon's performativity from Austin's and MacKenzie's (Section 4.2), which was a concern shared with Reviewer 3. The theoretical architecture is now load-bearing rather than decorative.

**Concern 3 -- Computational corpus analysis underspecified: PARTIALLY RESOLVED**

The reflexive paragraph added to the introduction -- acknowledging that the embedding-based method is itself "an act of commensuration in Espeland and Stevens's sense" -- is a genuine improvement. It signals methodological self-awareness appropriate for this journal's readership. However, my original concern was not solely about reflexivity; it was also about specification. The manuscript still does not provide, within its own pages, enough detail for a reader to evaluate the computational claims. How were the six thematic clusters determined? What motivated the choice of sentence-transformer embeddings over alternatives? What is the sensitivity of the "structural break" detection to parameter choices? The author directs readers to a GitHub repository and a technical report, which is reasonable for a humanities journal, but a brief paragraph (four to five sentences) specifying the clustering method, the break-detection algorithm, and any robustness checks would strengthen the evidential standing of the corpus subsections without adding excessive length. As it stands, the reader must take on faith that "cosine divergence" and "Jensen-Shannon divergence" tests are well-calibrated -- a posture somewhat at odds with the paper's own argument about the politics of measurement.

**Concern 4 -- "Two communities" claim needs stronger evidence: PARTIALLY RESOLVED**

The manuscript now provides Gaussian mixture model statistics (delta-BIC values of -12 for crystallization, 864 for post-2015) to support the bimodality claim. This is more rigorous than the first draft. The characterisation of the two poles -- efficiency (leverage, de-risking, blended finance) versus accountability (additionality, climate justice, grant-equivalent) -- is substantively convincing and well-illustrated by the OECD-Oxfam dispute in Section 3.3. However, the claim remains primarily computational. The paper would benefit from at least one passage identifying named scholars or institutional actors who consciously identify with or contest this division. Do practitioners at the OECD recognise themselves as belonging to an "efficiency pole"? Do Oxfam researchers frame their work as "accountability"? Without some evidence that the bimodality is not merely a statistical artefact of topic-modelling but corresponds to a division recognised by participants, the claim hovers between a finding and an imposition.

**II. Assessment of New Changes**

The revisions are, on the whole, well-executed. Several specific improvements deserve mention. The acknowledgement in Section 2.4 that "the demand for quantification came from G77+China negotiators" is an important correction that makes the paper's central thesis -- economists as category-makers -- more precise and more defensible. The addition of Star and Griesemer's boundary objects concept (Section 4.3) strengthens the theoretical vocabulary and provides a better fit than Gieryn alone for describing climate finance categories that are shared across communities. The qualification in Section 3.4 distinguishing semantic stability from institutional change (acknowledging the Enhanced Transparency Framework and the TCFD) addresses a concern raised by Reviewer 2 and makes the "no break at Paris" claim more credible.

One new issue: the condensation of Section 4 has made it quite dense. The merged subsection on commensuration and economization (Section 4.1) treats these as near-synonyms, but the paper's own narrative suggests they operate at different levels -- commensuration as a cognitive operation, economization as an institutional process. A single clarifying sentence distinguishing the two would prevent readers from collapsing them entirely.

**III. Remaining Issues**

1. A brief in-text specification of the computational method (clustering algorithm, break-detection procedure, robustness) would close the remaining methodological gap.
2. The "two communities" claim would benefit from one or two sentences grounding the bimodality in actors' own self-understanding, not only in statistical patterns.
3. The limitation regarding absent prosopography should be stated more directly.
4. Section 4.1 should briefly distinguish commensuration from economization rather than treating them as interchangeable.

None of these require major structural changes. All can be addressed in a careful line-edit.

**IV. Recommendation: MINOR REVISION**

The manuscript has improved substantially. The theoretical framework is now integrated into the historical narrative. The performativity vocabulary has been clarified. The "economists as architects" thesis has been appropriately qualified. The remaining issues are matters of precision and specification, not of structure or argument. I recommend acceptance after a minor revision addressing the four points listed above.

---

## Reviewer 2 — Climate Finance Policy

**REFEREE REPORT -- ROUND 2**

**Reviewer 2 (Climate finance policy and international development)**

**Manuscript:** "Counting Climate Finance. How Economists Made a Governable Object (1990-2025)"

**Journal:** *Oeconomia -- History / Methodology / Philosophy*

---

**1. Status of Round 1 Concerns**

**Concern 1 (Economists as architects -- missing actors): RESOLVED.**
The revised section 2.4 now explicitly states that "the demand for quantification came from G77+China negotiators and civil-society organisations who insisted that pledges be measurable and verifiable, and the political targets themselves were set by heads of state." This is a significant improvement. The paragraph now properly distinguishes between the political mandate (which came from elsewhere) and the technical construction (which economists performed). The formulation that economists provided the "quantitative grammar" while others set the agenda is both accurate and elegant. I am satisfied.

**Concern 2 (No break at Paris -- too strong): RESOLVED.**
The opening of section 3.4 now carries a clear qualification distinguishing semantic stability from institutional architecture, acknowledging that the Enhanced Transparency Framework moved reporting from voluntary to mandatory, and that the TCFD represented a "genuinely new application not prefigured during crystallization." This is precisely the nuance I requested. The claim is now defensible: what persisted was the conceptual vocabulary, not the institutional landscape. The revised formulation also avoids the risk that a reader in the policy community would dismiss the paper as claiming nothing changed after 2015.

**Concern 3 (Missing institutions -- GCF, MDBs, IDFC, CPI): PARTIALLY RESOLVED.**
Section 3.1 now includes a passage on MDB joint climate finance tracking and the GCF's investment framework, characterized as "competing commensurations [that] coexisted rather than converged." This is a welcome addition and strengthens the argument that the OECD/DAC framework was dominant but not monopolistic. However, the IDFC (International Development Finance Club) remains absent, as the author acknowledges. Given that the IDFC represents 27 national and regional development banks, many from the Global South, and publishes its own climate finance tracking reports using yet another methodology, this omission is worth noting. That said, the paper cannot discuss every institution. The MDB and GCF additions sufficiently demonstrate the coexistence of multiple measurement regimes, which was my core analytical point. I will not press further on IDFC, though a footnote acknowledging its existence would strengthen the paper's credibility with specialist readers. The CPI's role is well represented throughout (sections 2.5, 3.2, 3.3, 4.1).

**Concern 4 (Efficiency/accountability binary oversimplifies): PARTIALLY RESOLVED.**
The author has not directly restructured the binary, but section 3.4 now notes that "the accountability pole remains occupied -- indeed, it has become more internally differentiated, with new sub-literatures on loss and damage, climate debt, and just transition." This is a step in the right direction. The statistical apparatus (Gaussian mixture modelling, BIC comparisons) does support bimodality as an empirical finding, and I accept that this is the structure the corpus analysis reveals. My residual concern is interpretive rather than empirical: characterizing the entire field as organized around two poles risks flattening the work of scholars and institutions that operate across the divide -- for instance, MDB practitioners who simultaneously pursue leverage and accountability, or researchers like Steckel who propose dissolving the boundary entirely. Section 4.4 calls the tension "productive rather than pathological," which is helpful but still treats it as a stable axis rather than a contested and shifting one. This is a minor point and should not hold up publication.

---

**2. Assessment of New Changes**

Beyond my specific concerns, the revision has improved markedly in several respects. The integration of theory into the historical narrative (responding to Reviewers 1 and 3) has tightened the argument considerably. Performativity is now used with appropriate precision, anchored explicitly in Callon rather than floating between Austin, Callon, and MacKenzie. The reflexive note on the paper's own method as an act of commensuration is intellectually honest and appropriate for this journal's readership. The addition of Star and Griesemer on boundary objects strengthens section 4.3 and makes the theoretical apparatus more robust. The condensation of Section 4 from approximately 1,500 to 800 words eliminates redundancy without losing substance.

The paper is now approximately 8,400 words with 50 bibliography entries. This is a well-proportioned manuscript for Oeconomia.

---

**3. Remaining Issues (Minor)**

(a) **IDFC footnote.** As noted above, a single footnote acknowledging the IDFC's climate finance tracking would close a gap visible to specialist readers. This requires one sentence, not a paragraph.

(b) **The "two traditions" claim in section 4.4.** The assertion that climate finance was "assembled from two traditions (market-based environmental economics and equity-oriented development economics)" is stated as fact but not demonstrated in the paper. Development economics is not a monolith, and many accountability-oriented scholars come from political science, international relations, or law rather than economics. A qualifying phrase -- "broadly understood" or "among others" -- would prevent overstatement.

(c) **Post-2024 developments.** The manuscript closes with the Baku NCQG (November 2024). Given the submission date of March 2026, the reader may wonder whether early implementation of the NCQG or the first round of ETF reporting (due 2024) has produced any evidence relevant to the stability thesis. If no such evidence exists yet, a sentence saying so would be appropriate. If it does, even a brief mention would demonstrate currency.

---

**4. Recommendation: MINOR REVISION**

The author has substantively addressed three of my four major concerns and partially addressed the fourth. The revisions are not cosmetic; they represent genuine analytical refinement. The remaining issues (a)-(c) above are minor and can be addressed without restructuring the argument. I recommend acceptance after minor revision. The paper makes a valuable contribution to the history of economic thought on climate policy, and its computational methodology, now appropriately qualified, offers a model for similar studies in the history of economics.

---

## Reviewer 3 — STS & Sociology of Quantification

**REFEREE REPORT -- Round 2**

**Reviewer 3 (STS / sociology of quantification / performativity)**

**Manuscript:** "Counting Climate Finance. How Economists Made a Governable Object (1990--2025)"

---

### 1. Status of Round 1 Concerns

**Concern 1 (Theory separated from narrative): RESOLVED.**
The revision successfully integrates theoretical concepts at their point of narrative relevance. Commensuration is introduced in section 1.2 through the DAC statistical conventions and Desrosieres, performativity appears in section 2.1 at the Copenhagen moment, economization enters in section 2.2 with the OECD infrastructure-builders, and boundary work is deployed in section 3.2 alongside the Oxfam Shadow Reports. Section 4 now reads as a genuine recapitulation rather than a belated first exposition. The back-references in section 4's opening sentence ("that we have named as they appeared in the narrative") make the architecture explicit. This is a significant improvement. The concepts now do analytical work in the historical sections rather than arriving as post-hoc labels.

**Concern 2 (Performativity used imprecisely): RESOLVED.**
The revision addresses this concern with appropriate specificity. In section 2.1, the Copenhagen commitment is now described as "performative in Callon's sense: a declaration that, by triggering the construction of measurement infrastructure, brought into existence the very object it promised to deliver." This correctly identifies the mechanism as institutional formatting rather than illocutionary force. Section 4.2 explicitly distinguishes Callon's sense from MacKenzie's Barnesian performativity, noting that "the mechanism here is institutional rather than market-based." The Austin conflation has been removed. I would have welcomed a sentence acknowledging that even Callon's framework was developed primarily for market devices, and that applying it to intergovernmental accounting infrastructure represents a deliberate extension -- but this is a refinement, not a deficiency. The concept is now used with adequate precision for a history-of-economic-thought article.

**Concern 3 (Epistemological tension between corpus method and STS constructivism): RESOLVED.**
The reflexive paragraph added to the introduction is well-crafted. The formulation that the embedding space "renders comparable what was written in different languages, disciplines, and institutional contexts" and constitutes "one more measurement apparatus whose conventions shape what it makes visible" directly applies Espeland and Stevens's commensuration framework to the paper's own method. This is not perfunctory throat-clearing; it genuinely positions the computational analysis as a form of commensuration subject to the same constructivist scrutiny the paper applies to its object. The subordination of corpus evidence to the historical argument ("exploratory evidence supporting the historical interpretation, not the reverse") further mitigates the tension. The paper now holds a coherent epistemological position: the computational patterns are treated as corroborative signals produced by an acknowledged apparatus, not as objective descriptions.

**Concern 4 (Economization lacking analytical weight distinct from commensuration): PARTIALLY RESOLVED.**
The merger of commensuration and economization in section 4.1 is an honest response -- acknowledging their overlap rather than artificially inflating the distinction. The formulation that the DAC conventions are "simultaneously infrastructures of commensuration" and "infrastructures of economization" is accurate. However, this very merger raises a question the paper does not quite answer: if the two concepts are so overlapping that they must be treated together, what does economization add that commensuration alone does not provide? The paragraph gestures at an answer -- economization names the transformation of a "diplomatic and environmental problem into something calculable, governable, and amenable to financial reasoning" -- but this is close to what commensuration already does in Espeland and Stevens's account. The addition of Merry (2016) enriches the commensuration side but does not sharpen the economization side. Caliskan and Callon's distinctive contribution is the emphasis on how "the economy" itself is enacted through distributed calculative practices; the paper could strengthen section 4.1 by noting that what economization adds is precisely the claim that the climate finance domain was not merely measured but constituted *as economic* -- that is, made amenable to a specific form of governance (financial reasoning, cost-benefit assessment, leverage calculation) that forecloses other framings (reparative justice, ecological debt). One or two sentences would suffice.

### 2. Assessment of New Changes

The additions of Star and Griesemer (boundary objects) and Weikmans and Roberts are well-placed. The characterisation of climate finance categories as "boundary objects shared across communities with different interpretations while maintaining enough identity to coordinate action" (section 4.3) is analytically productive and better captures the empirical reality than Gieryn's boundary work alone. These two concepts now do distinct work: boundary objects names the shared categorical infrastructure, boundary work names the contests over its application. This is a genuine theoretical improvement.

The deferred item on the Foucauldian grounding of "governable object" is acceptable. The author's position -- that the phrase is used in its ordinary English sense -- is defensible, though readers of this journal will inevitably hear Miller and Rose. A brief footnote acknowledging the resonance without committing to the full governmentality apparatus would be prudent but is not essential.

### 3. Remaining Minor Issues

(a) Section 4.2 states that the Copenhagen target mechanism is "distinct from MacKenzie's Barnesian performativity, where financial models make the world conform to their predictions." This is slightly compressed. MacKenzie's taxonomy distinguishes generic, effective, and Barnesian performativity; the paper invokes only the last. A parenthetical reference to MacKenzie (2006, ch. 1) would signal awareness of the full taxonomy without requiring exposition.

(b) The conclusion's final paragraph mentions that "Dahan (2010) has shown how models function as 'boundary objects' in climate governance" and suggests extending the analysis to accounting standards. This is a productive suggestion, but it comes very late and risks appearing as an afterthought. Consider moving or cross-referencing it in section 4.3 where boundary objects are discussed, so the connection to existing STS literature on climate governance is visible at the point where it matters analytically.

(c) The paper now cites 50 references for approximately 8,400 words. The bibliography is well-curated. I do not insist on the addition of Rottenburg et al. (2015) or Davis et al. (2012), but a single citation to the governance-by-indicators literature in section 4.1 alongside Merry would further anchor the argument for STS-literate readers.

### 4. Recommendation

**Minor revision.** The three major concerns from Round 1 have been resolved. The fourth (economization's analytical distinctiveness) is partially resolved; the merger with commensuration is defensible but would benefit from two sentences clarifying what economization adds. The remaining issues are minor and can be addressed without further review. The paper makes a genuine contribution to the history of economic thought by demonstrating how category-making, rather than modelling, constituted climate finance as an object of governance. The theoretical apparatus is now integrated into the narrative with sufficient precision to satisfy an STS-informed readership.

---

## Editorial Synthesis — Remaining Items for Minor Revision

All three reviewers have moved from **Major revision** (Round 1) to **Minor revision** (Round 2).

### Resolved issues (Round 1 → Round 2)

| Issue | R1 | R2 | R3 |
|-------|:--:|:--:|:--:|
| Theory integrated into narrative | RESOLVED | — | RESOLVED |
| Performativity sharpened | RESOLVED | — | RESOLVED |
| "Economists as architects" qualified | RESOLVED | RESOLVED | — |
| "No break at Paris" qualified | — | RESOLVED | — |
| Reflexive note on method | PARTIALLY | — | RESOLVED |
| Missing institutions (GCF, MDBs) | — | PARTIALLY | — |

### Remaining minor items

1. **Brief computational method specification** (R1): 4-5 sentences on clustering algorithm, break detection, robustness
2. **Economization vs commensuration** (R3): 2 sentences clarifying what economization adds (domain constituted *as economic*, not merely measured)
3. **Two-communities grounding** (R1): 1-2 sentences showing actors recognise the efficiency/accountability divide
4. **IDFC footnote** (R2): single footnote acknowledging its existence
5. **Dahan (2010) cross-reference** (R3): move mention to §4.3 where boundary objects are discussed
6. **"Two traditions" qualifier** (R2): add "broadly understood" to the claim about market-based vs equity-oriented origins
7. **MacKenzie taxonomy** (R3): parenthetical reference to his full taxonomy in §4.2
8. **Prosopography limitation** (R1): make more explicit in limitations paragraph
