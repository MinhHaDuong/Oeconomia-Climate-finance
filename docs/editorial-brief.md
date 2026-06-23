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

**Ticket:** memory `feedback_oversell_breaks`.

**Status:** active

## named-actors-not-policymakers

**Decision:** Name the specific economists and institutions responsible for a
category or claim (OECD DAC, CPI, the Standing Committee on Finance) rather than
generic agents ("policymakers", "stakeholders", "the international community").

**Rationale:** History of economic thought attributes category-making to
identifiable actors with motivations; generic agents erase the economist's role
the paper is tracing.

**Ticket:** `.claude/rules/writing.md` (citation practices).

**Status:** active

## define-at-first-use

**Decision:** Define each technical term (concessionality, mobilised private
finance, Rio markers, additionality) at its first appearance.

**Rationale:** The venue is interdisciplinary (HET + STS + policy studies); a
term obvious to a climate-finance economist is opaque to a historian of
economics, and vice versa.

**Ticket:** `.claude/rules/writing.md` (voice and style).

**Status:** active

## het-register-not-motivational

**Decision:** Hold an HET academic register — clear and concrete, *Economist*
ghost-mode — without American motivational or business-book cadence (no "this is
what X is", punchy one-beat sentences, or pep-talk closers).

**Rationale:** The target venue is Œconomia. The motivational register reads as
machine-written and is out of place in a history-of-economic-thought article.

**Ticket:** memory `feedback_het_register`; `.claude/rules/writing.md` (ghost mode).

**Status:** active

## north-south-specificity

**Decision:** Show North–South divides through specific actors and their
motivations, not as a monolithic binary.

**Rationale:** "The Global South wants X" flattens a contested field; the paper's
contribution is to show which actors pushed which categories and why.

**Ticket:** `.claude/rules/writing.md` (things to avoid).

**Status:** active
