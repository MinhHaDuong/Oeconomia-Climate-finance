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

Add more perspectives when warranted (e.g., **Security** for auth changes, **Performance** for data pipeline changes, **Historiography** for manuscript claims).

### Proportional depth

Not every PR needs every agent. Scale to risk:

| PR size / risk | Agents to launch |
|---|---|
| Trivial (typo, comment, config) | Correctness only |
| Standard (single-file logic, prose edits) | Correctness + Consistency |
| Substantial (multi-file, new feature, pipeline change) | All four core agents |
| High-risk (schema change, methodology change) | All four + domain-specific agents |

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

## What to look for (all perspectives)

- Does every changed file have a reason in the commit message?
- Are there new files that should be in .gitignore?
- Do commit messages explain *why*, not just *what*?
- Any secrets, large files, or conflict markers? (hook should catch, but verify)
- Any blacklisted AI-tell words introduced? (`make lint-prose`)
