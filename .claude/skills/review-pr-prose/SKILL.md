---
name: review-pr-prose
description: Simulated peer review panel for manuscript prose. Spins discipline-specific agents for multi-perspective review.
disable-model-invocation: false
user-invocable: true
argument-hint: <pr-number>
context: fork
---

# Review PR prose $ARGUMENTS — simulated peer review panel

Spin disciplinary agents in parallel, each in a fresh context. Prose review reads **full text**, not just diff.

## Setup

1. Identify the text: which `.qmd`/`.md` files changed? What is the target venue?
2. Read the diff: `gh pr diff $ARGUMENTS`
3. Select the panel from templates below.

## Panel templates

### Oeconomia manuscript (HPS journal)

| Agent | Focus | Key question |
|---|---|---|
| **Historian of economics** | Historical accuracy, periodization, actors | Claims grounded in specific dates, documents, people? |
| **STS / constructivism** | Category-making, co-production, performativity | Shows how the object was constructed? |
| **Climate policy specialist** | Institutional accuracy, missing actors, policy nuance | Would practitioners recognize this account? |
| **Literature specialist** | Deep research on cited/uncited works | Key references missing? Recent contradictions? |
| **Adversarial referee** | Logical gaps, unsupported claims, rhetorical overreach | Where exactly does the argument fail? |
| **Copy editor** | AI tells, blacklist words, house style | Passes writing rules and oeconomia-style rules? |

### Technical report

Scientometrician, Replicator, Literature specialist, Adversarial referee, Copy editor.

### Custom panels

One perspective per audience segment. Always include: Literature specialist + Adversarial referee + Copy editor.

## Each agent runs

1. Read the **full text** (not just the diff).
2. **Literature specialist** does actual web searches and cites specific papers.
3. **Adversarial referee** quotes specific sentences and explains why they fail.
4. Report **confidence** + **severity** (major / minor / suggestion).
5. Verdict: **accept**, **minor revision**, or **major revision**.

## Synthesis

1. Preserve dissent verbatim.
2. Group findings: major (blocks acceptance), minor (should fix), suggestion.
3. Deduplicate convergent findings.
4. Run `make lint-prose` and `make manuscript`.
5. Check consistency with `content/*-vars.yml`, figures, tables.
6. Post single review via `gh pr review`.

## Proportional depth

| Text change | Panel size |
|---|---|
| Typo, citation fix | Copy editor only |
| Section rewrite | 3 agents (domain + adversarial + copy) |
| Full paper draft | Full panel (5-6 agents) |
| Submission-ready | Full panel + response-to-reviewers template |
