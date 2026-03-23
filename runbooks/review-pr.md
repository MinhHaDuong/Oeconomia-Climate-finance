# Review PR — multi-perspective agent review

A review means spinning multiple agents in parallel, each with a distinct perspective. Run all agents in fresh contexts (no shared history with the implementing agent).

## Setup

1. **Read the issue** linked to the PR. Note the exit criteria.
2. **Read the diff**: `gh pr diff <number>`
3. **Launch review agents** in parallel (each in its own worktree):

| Agent perspective | Focus | Key question |
|---|---|---|
| **Correctness** | Logic, edge cases, test coverage | Does this do what the exit criteria say? |
| **Consistency** | Style, naming, docs, stale references | Does this fit the rest of the codebase? |
| **Scope** | Over-engineering, unrelated changes, feature creep | Does this change *only* what the ticket asks? |
| **Red team** | Adversarial inputs, broken invariants, failure modes | How can this break? |
| **Doc propagation** | Downstream text accuracy | Do docs, papers, and configs still match the code? |

The **Doc propagation** agent is **mandatory** whenever the PR touches pipeline scripts (`scripts/`), configuration, methodology, or data contracts. It is not optional — omitting it is a review defect. Add more perspectives when warranted (e.g., **Security** for auth changes, **Performance** for data pipeline changes, **Historiography** for manuscript claims).

### Documentation propagation agent

This agent asks: **"What docs, configs, and downstream reports reference the changed behavior — are they still accurate?"**

A PR that changes pipeline behavior without updating the docs that describe it is **incomplete**. The doc propagation agent's verdict carries the same weight as correctness — a stale doc that misleads a reader is a bug.

Checklist:
1. **Trace references** — search for mentions of changed functions, parameters, file names, or concepts in:
   - `content/technical-report.qmd` (pipeline methodology for replicators)
   - `content/data-paper.qmd` (dataset description for journal readers)
   - `content/manuscript.qmd` and its `_includes/` (claims for Oeconomia readers)
   - `content/*-vars.yml` (per-document computed values cited in prose)
   - `docs/` (coding/writing guidelines, style guides)
   - `README.md`, `STATE.md`, `ROADMAP.md`
   - Configuration files (`corpus_collect.yaml`, `dvc.yaml`, `Makefile`)
2. **Flag stale references** — any doc that describes the old behavior is a finding.
3. **Check hardcoded numbers** — search for counts, percentages, or statistics in prose that may have changed (e.g., "15 institutions", "87 readings", "130 courses").
4. **Verdict**: request-changes if a downstream doc would mislead a reader; comment if the staleness is cosmetic.

### Proportional depth

Not every PR needs every agent. Scale to risk:

| PR size / risk | Agents to launch |
|---|---|
| Trivial + user present | **Skip PR entirely** — branch → commit → `git merge --no-ff -m` → push main |
| Trivial (typo, comment, config) | Correctness only |
| Standard (single-file logic, prose edits) | Correctness + Consistency |
| Standard + touches `scripts/` | Correctness + Consistency + **Doc propagation** |
| Substantial (multi-file, new feature, pipeline change) | All five agents (Correctness + Consistency + Scope + Red team + **Doc propagation**) |
| High-risk (schema change, methodology change) | All five + domain-specific agents (Historiography, Performance, etc.) |

## Each agent runs

1. Read the issue exit criteria and the diff.
2. Evaluate the PR from its assigned perspective.
3. For each finding, report **confidence** (high / medium / low). Low-confidence findings need deeper investigation during synthesis — they are not dismissed.
4. Return a structured verdict: **approve**, **comment**, or **request-changes**, with specific findings.

## Synthesis

After all agents return:

1. **Preserve dissent** — when agents contradict each other, surface both positions verbatim. Do not average or silently pick a winner. The human author decides.
2. **Triage by confidence** — investigate low-confidence findings before posting. Promote or dismiss them with reasoning.
3. **Merge findings** — deduplicate, note where scope agent flags what correctness agent requested.
4. **Run tests**: `make check` (lint-prose + pytest).
5. **Run build**: `make manuscript` (if prose changed).
6. **Check for stale info**: are STATE.md, ROADMAP.md, docs/* consistent with the changes?
7. **Post a single review**: `gh pr review <number> --comment --body "..."` or `--approve` / `--request-changes`. Attribute each finding to its perspective and confidence level.

## Code-quality escalation policy

Not every problem must be fixed in the current PR. Escalate according to origin:

| Severity | Rule | Action |
|---|---|---|
| **Blocks correctness** (bug, data loss, silent failure) | Fix before merge | request-changes |
| **Introduced by this PR** (new smell, new anti-pattern, over-engineering) | Fix before merge — you own what you create | request-changes |
| **Pre-existing but touched by this PR** (edited a smelly function, extended an anti-pattern) | Don't block the PR; file a follow-up ticket | comment + new ticket |
| **Pre-existing and untouched** (noticed while reviewing nearby code) | Delegate to an investigation agent | agent → assess → file ticket if warranted, drop with reason if not |

**Principle: you own what you touch, you don't own what you read** — but what you read still gets triaged, because investigation is cheap.

### What qualifies as a code-quality finding

- **Code smell**: dead code, duplicated logic, god functions, deep nesting, magic numbers.
- **Anti-pattern**: reinventing stdlib, mutation in a pipeline, silent exception swallowing, stringly-typed interfaces.
- **Over-engineering**: premature abstraction, speculative generality, unnecessary indirection, configuration for things that don't vary.

### Delegation protocol for pre-existing issues

When a reviewer spots a pre-existing issue in untouched code:

1. **Spawn an investigation agent** (fresh context, read-only).
2. The agent checks: Is this already tracked in an open issue? Is it intentional (documented trade-off)? How severe is the impact?
3. If warranted → agent files a ticket following `runbooks/new-ticket.md`.
4. If not warranted → agent comments with the reasoning (why it's acceptable or out of scope).
5. The reviewer does not block the PR for pre-existing issues — focus stays on the diff.

## What to look for (all perspectives)

- Does every changed file have a reason in the commit message?
- Are there new files that should be in .gitignore?
- Do commit messages explain *why*, not just *what*?
- Any secrets, large files, or conflict markers? (hook should catch, but verify)
- Any blacklisted AI-tell words introduced? (`make lint-prose`)
