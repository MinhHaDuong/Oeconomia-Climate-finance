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
3. Recruit the panel: select agents appropriate for the venue and scope of changes. Always include an adversarial referee. Add a journal-specific expert if venue rules exist (check `.claude/rules/`).

## Each agent runs

1. Read the **full text** (not just the diff).
2. Report **confidence** + **severity** (major / minor / suggestion).
3. Verdict: **accept**, **minor revision**, or **major revision**.

Agents with relevant expertise should use available tools (web search for literature, linting tools if installed, etc.).

## Synthesis

1. Preserve dissent verbatim.
2. Group findings: major (blocks acceptance), minor (should fix), suggestion.
3. Deduplicate convergent findings.
4. Build the manuscript. Check consistency between prose and data.
6. Post single review via `gh pr review`.

## Proportional depth

| Text change | Panel size |
|---|---|
| Typo, citation fix | Copy editor only |
| Section rewrite | 3 agents (domain + adversarial + copy) |
| Full paper draft | Full panel (5-6 agents) |
| Submission-ready | Full panel + response-to-reviewers template |
