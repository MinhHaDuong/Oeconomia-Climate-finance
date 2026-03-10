# Response to Reviewers — Round 2

**Manuscript:** "Counting Climate Finance. How Economists Made a Governable Object (1990–2025)"
**Target journal:** *Œconomia — History / Methodology / Philosophy*
**Date:** 2026-03-10

We thank the three reviewers for their positive reassessment and for confirming that the major concerns from Round 1 have been resolved. All three now recommend minor revision. Below we describe the proposed changes for the eight remaining items, organised by reviewer convergence.

---

## 1. Brief computational method specification (R1 item 1 — §1 or methods paragraph)

**Request:** 4–5 sentences specifying the clustering algorithm, break-detection procedure, and robustness checks, so that readers need not consult the GitHub repository to evaluate the computational claims.

**Proposed change:** Add a paragraph to the introduction's methodological section:

> The 22,113 works were embedded using a multilingual sentence-transformer (all-MiniLM-L6-v2). Thematic clusters were identified via Gaussian mixture modelling on the first 50 principal components, with model order selected by Bayesian Information Criterion (BIC). Structural breaks in vocabulary composition were detected by computing Jensen–Shannon divergence between successive annual distributions and testing significance against a bootstrap null. The six-cluster solution is robust to alternative embeddings (multilingual-e5-base) and to ±2-year shifts in the break-point search window. Full replication code is available at [repository URL].

**Word cost:** ~80 words.

---

## 2. Economization vs commensuration distinguished (R1 item 4, R3 item on §4.1)

**Request:** Clarify what economization adds beyond commensuration. Both reviewers converge: R1 asks for a "single clarifying sentence," R3 proposes 1–2 sentences noting that economization constitutes the domain *as economic*, foreclosing non-economic framings.

**Proposed change:** Add to §4.1, after the existing sentence on overlap:

> What economization adds to commensuration is a claim about the *kind* of governance that measurement enables. Commensuration makes things comparable; economization makes them amenable to financial reasoning—cost-benefit assessment, leverage calculation, de-risking ratios—thereby constituting the climate problem as economic and foreclosing framings centred on reparative justice or ecological debt.

**Word cost:** ~50 words.

---

## 3. Two-communities grounding in actors' self-understanding (R1 item 2)

**Request:** 1–2 sentences showing the efficiency/accountability divide is recognised by participants, not merely a statistical artefact.

**Proposed change:** Add to §3.3 or §4.4, after the bimodality statistics:

> This division is not merely computational. It is explicitly articulated by participants: OECD reports frame climate finance as a tool for "mobilising" and "leveraging" private capital, while Oxfam's assessments define their purpose as "holding donors to account" for the adequacy and quality of their pledges.

**Word cost:** ~45 words.

---

## 4. IDFC footnote (R2 item a)

**Request:** Acknowledge the IDFC's existence and its independent climate finance tracking.

**Proposed change:** Add a footnote in §3.1, after the MDB joint tracking passage:

> The International Development Finance Club (IDFC), representing 27 national and regional development banks largely from the Global South, publishes its own annual Green Finance Mapping using categories that overlap with but do not replicate the OECD/DAC framework.

**Word cost:** ~35 words (footnote).

---

## 5. Dahan (2010) cross-reference to §4.3 (R3 item b)

**Request:** The Dahan mention in the conclusion comes too late; cross-reference it in §4.3 where boundary objects are discussed.

**Proposed change:** Add a sentence in §4.3 after the Star & Griesemer discussion:

> The concept has prior purchase in climate scholarship: Dahan (2010) showed that climate models themselves function as boundary objects across science and governance. Here we extend the analysis from models to accounting categories.

Move the concluding mention to a back-reference: "As noted in §4.3, Dahan (2010) has shown…"

**Word cost:** ~30 words (net neutral, redistributed).

---

## 6. "Two traditions" qualifier (R2 item b)

**Request:** The claim that climate finance was "assembled from two traditions" overstates disciplinary homogeneity. Add a qualifier.

**Proposed change:** Revise the sentence in §4.4:

> "assembled from two broad intellectual orientations—market-oriented environmental economics and equity-oriented development studies—**among other disciplinary tributaries including international law, political science, and international relations**"

**Word cost:** ~15 words.

---

## 7. MacKenzie taxonomy parenthetical (R3 item a)

**Request:** The paper invokes only Barnesian performativity; a parenthetical reference to MacKenzie's full taxonomy (generic, effective, Barnesian) would signal awareness.

**Proposed change:** In §4.2, after "MacKenzie's Barnesian performativity," add:

> (MacKenzie 2006, ch. 1, distinguishes generic, effective, and Barnesian performativity; we invoke the last)

**Word cost:** ~15 words.

---

## 8. Prosopography limitation made explicit (R1 item 3)

**Request:** The limitations paragraph should directly state the absence of archival/interview evidence as a constraint on claims about individual motivation.

**Proposed change:** Add to the limitations paragraph in the conclusion:

> In particular, our account of economists as institutional architects rests on published outputs rather than archival records or interviews; claims about individual motivations and deliberative processes remain conjectural until primary-source research is undertaken.

**Word cost:** ~30 words.

---

## Items noted but not proposed for this revision

- **Governance-by-indicators literature** (R3 item c): Rottenburg et al. (2015) or Davis et al. (2012). R3 does not insist. We will add if the editor requests.
- **Post-2024 ETF/NCQG developments** (R2 item c): The first biennial transparency reports are due December 2024; as of our submission date, no comprehensive assessment of their impact on measurement categories has been published. We propose adding a sentence noting this.
- **Foucauldian footnote** for "governable object" (R3): R3 calls it "prudent but not essential." We propose a brief footnote acknowledging the resonance with Miller & Rose without adopting the full governmentality apparatus.

---

## Summary of proposed changes

| Item | Section | Word cost | Reviewer |
|------|---------|-----------|----------|
| Computational method specification | §1 (methods) | +80 | R1 |
| Economization vs commensuration | §4.1 | +50 | R1, R3 |
| Two-communities grounding | §3.3/4.4 | +45 | R1 |
| IDFC footnote | §3.1 (fn) | +35 | R2 |
| Dahan cross-reference | §4.3 | ±0 | R3 |
| "Two traditions" qualifier | §4.4 | +15 | R2 |
| MacKenzie taxonomy | §4.2 | +15 | R3 |
| Prosopography limitation | Conclusion | +30 | R1 |
| **Total** | | **~270** | |

Net word count after changes: ~8,670 words. Well within typical Œconomia limits.

All changes are line-edits addressable in a single pass. No structural revision required.
