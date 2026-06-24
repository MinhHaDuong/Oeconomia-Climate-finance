# Editorial brief — standing editorial decisions

Standing editorial decisions for `content/manuscript.qmd`. CI enforces only
mechanical checks and *negative* guards (forbidden phrasings — see
`tests/test_manuscript_prose.py`); the positive intent behind each decision
lives here and is checked at review time by the `/review-pr-prose` panel against
every manuscript diff (CI test-polarity rule, `.claude/rules/writing.md`).

Entry format: one H2 per decision, slug-style heading, with **Decision:** /
**Rationale:** / **Ticket:** / **Status:**. The first three fields are the
schema the `/review-pr-prose` brief auditor consumes; **Status:** is bookkeeping
local to this file. A decision is retired by flipping **Status:** to
`retired (reason)`, never by deleting the entry.

Governance note: LLM reductions of manuscript prose (descaffold, abstract
realign, summary verdicts) must clear the four reduction guards in
`scripts/qa_llm_judge_guards.py` — output no longer than input, zero em dashes,
no invented number, no LLMism introduced — before their output is trusted.

## construction-not-discovery

**Decision:** Prose frames climate finance as a constructed economic object —
economists *built* the accounting categories — and never as a pre-existing
reality that was discovered or revealed.

**Rationale:** This is the manuscript's central thesis. "Climate finance grew",
"emerged naturally", or "was found to be" smuggles in the realist framing the
paper exists to dismantle.

**Ticket:** 0135 (reframe the economists' claim); `.claude/rules/writing.md`.

**Status:** active

## periodization-corroborated-not-endogenous

**Decision:** Present the three-act periodization as history-first and
*corroborated* by the break detection. Never describe the periodization as
"endogenous", "data-driven", or "not imposed from the COP calendar".

**Rationale:** The detection is confirmatory, not constitutive — it is blind to
the policy timeline, so an independent 2007/2009 break is corroboration. Calling
it endogenous overclaims and contradicts the confirmatory framing.

**Ticket:** 0161 (manuscript statistics audit); memory `feedback_oversell_breaks`.

**Status:** active

## paris-rise-real-not-null

**Decision:** Treat the mid-2010s Jensen–Shannon rise as a real, marginal
signal. Never claim "Paris did not matter" or that 2015 produced no change.

**Rationale:** The thesis predicts post-2015 disputes *within* crystallized
categories — a marginal rise, not a rupture. Denying the rise outright
overcorrects and misreports the computation, which corroborates the history.

**Ticket:** none — memory `feedback_oversell_breaks`.

**Status:** active

## named-actors-not-policymakers

**Decision:** Name the specific economists and institutions responsible for a
category or claim (OECD DAC, CPI, the Standing Committee on Finance) rather than
generic agents ("policymakers", "stakeholders", "the international community").

**Rationale:** History of economic thought attributes category-making to
identifiable actors with motivations; generic agents erase the economist's role
the paper is tracing.

**Ticket:** none — `.claude/rules/writing.md` (citation practices).

**Status:** active

## define-at-first-use

**Decision:** Define each technical term (concessionality, mobilised private
finance, Rio markers, additionality) at its first appearance.

**Rationale:** The venue is interdisciplinary (HET + STS + policy studies); a
term obvious to a climate-finance economist is opaque to a historian of
economics, and vice versa.

**Ticket:** none — `.claude/rules/writing.md` (voice and style).

**Status:** active

## het-register-not-motivational

**Decision:** Hold an HET academic register — clear and concrete, *Economist*
ghost-mode — without American motivational or business-book cadence (no "this is
what X is", punchy one-beat sentences, or pep-talk closers).

**Rationale:** The target venue is Œconomia. The motivational register reads as
machine-written and is out of place in a history-of-economic-thought article.

**Ticket:** none — memory `feedback_het_register`; `.claude/rules/writing.md` (ghost mode).

**Status:** active

## north-south-specificity

**Decision:** Show North–South divides through specific actors and their
motivations, not as a monolithic binary.

**Rationale:** "The Global South wants X" flattens a contested field; the paper's
contribution is to show which actors pushed which categories and why.

**Ticket:** none — `.claude/rules/writing.md` (things to avoid).

**Status:** active

## economic-rationality-carried-by-economists

**Decision:** Attribute climate finance's construction to the diffusion of an
*economic mode of reasoning* — commensuration, leverage, attribution — carried
into institutional practice by economist-trained officials. Named actors
(Corfee-Morlot, OECD DAC staff) are the carriers of that rationality, not
evidence of a journal-publishing disciplinary guild. The economic *operations*
are the spine; the people are how they travelled.

**Rationale:** R1 §1 / editor E2: the named actors are policy professionals and
Table 2 shows no economics-journal venues, so an unqualified "economists built
it" is empirically exposed. The hybrid framing keeps the intellectual-history
claim (the operations performed were economic work — accounting, not modelling)
while conceding the actors were institutional.

**Ticket:** 0150 (v2.0.4 decision); gates 0135, 0139.

**Status:** active

## indeterminacy-as-political-resource

**Decision:** State as the explicit headline thesis that the
qualitative→quantitative translation is never fully determinate, and that this
indeterminacy made climate finance simultaneously *measurable* (a number exists)
and *contestable* (the number is always arguable) — a political resource every
side exploited, not a deficiency to be repaired. Frame the computation's role as
*confirmatory*: it corroborates a history-first reading. Never exploratory or
generative.

**Rationale:** R2's "potentially innovative" point + editor E4 require the thesis
stated up front and the quant role named. The claim already lives in §2 (the
categories that made climate finance countable also made it contestable); this
promotes it to thesis status. Confirmatory framing is the project's no-oversell
norm — cross-ref `periodization-corroborated-not-endogenous`.

**Ticket:** 0151 (v2.0.4 decision); gates 0136, 0137, 0134.

**Status:** active

## three-act-structure-foregrounds-ruptures

**Decision:** Keep the three-act periodization, but frame each act boundary
around its triggering institutional rupture (2007 Copenhagen commitment, the
2013/2015 turn) early, so the structure reads as rupture-driven rather than
calendar-driven. Decline Reviewer 2's full reorganisation in the cover letter,
justified by the corroborated rupture dates — never by calling the periodization
"endogenous" or "not imposed from the COP calendar".

**Rationale:** R2 general finds chronology unconvincing for so short a period.
The acts are already rupture-anchored (Act II = the Copenhagen trigger); the move
is to make that visible, not to rebuild. The "endogenous" guard cross-refs
`periodization-corroborated-not-endogenous`.

**Ticket:** 0142 (v2.0.4 decision); cover-letter response.

**Status:** active
