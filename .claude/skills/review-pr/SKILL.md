---
name: review-pr
description: Multi-perspective code review with parallel agents. Covers correctness, consistency, scope, red team, and doc propagation.
disable-model-invocation: false
user-invocable: true
argument-hint: <pr-number>
context: fork
---

# Review PR $ARGUMENTS — multi-perspective agent review

Spin multiple agents in parallel, each with a distinct perspective. Run all agents in fresh contexts.

## Setup

1. **Read the issue** linked to the PR. Note the exit criteria.
2. **Read the diff**: `gh pr diff $ARGUMENTS`
3. **Assess risk level** and determine proportional depth (see table below).
4. **On first review cycle**, add a risk label to the PR:
   - Trivial → add label `review:trivial` (merge gate requires 1 cycle)
   - Standard or above → add label `review:standard` (merge gate requires 2 cycles)
5. **Launch review agents** in parallel:

| Agent | Focus | Key question |
|---|---|---|
| **Correctness** | Logic, edge cases, test coverage | Does this do what the exit criteria say? |
| **Consistency** | Style, naming, docs, stale references | Does this fit the rest of the codebase? |
| **Scope** | Over-engineering, unrelated changes | Does this change *only* what the ticket asks? |
| **Red team** | Adversarial inputs, broken invariants | How can this break? |
| **Doc propagation** | Downstream text accuracy | Do docs, papers, and configs still match the code? |

**Doc propagation** is **mandatory** when the PR touches `scripts/`, configuration, methodology, or data contracts.

### Doc propagation checklist

Trace references in: `content/technical-report.qmd`, `content/data-paper.qmd`, `content/manuscript.qmd`, `content/*-vars.yml`, `docs/`, `README.md`, `STATE.md`, `ROADMAP.md`, `.claude/rules/architecture.md`, config files.

### Proportional depth

| PR risk | Agents |
|---|---|
| Trivial + user present | **Skip PR** — merge directly |
| Trivial (typo, config) | Correctness only |
| Standard | Correctness + Consistency |
| Standard + `scripts/` | + Doc propagation |
| Substantial | All five |
| High-risk (schema, methodology) | All five + domain experts |

## Each agent runs

1. Read the issue exit criteria and the diff.
2. Evaluate from its assigned perspective.
3. Report **confidence** (high / medium / low) per finding.
4. Return verdict: **approve**, **comment**, or **request-changes**.

## Synthesis

1. **Preserve dissent** — surface contradictions verbatim. The human author decides.
2. **Triage by confidence** — investigate low-confidence findings before posting.
3. **Deduplicate** findings across agents.
4. **Run tests**: `make check`
5. **Run build**: `make manuscript` (if prose changed)
6. **Post a single review** via `gh pr review`, attributing each finding to its perspective. Include `<!-- review-pr-marker -->` at the top of the review body for identification. The merge gate counts review objects posted by the agent, not markers.

## Code-quality escalation

| Severity | Action |
|---|---|
| Blocks correctness (bug, data loss) | request-changes |
| Introduced by this PR | request-changes |
| Pre-existing but touched | comment + new ticket |
| Pre-existing and untouched | investigate → ticket if warranted |
