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

Add more perspectives when warranted (e.g., **Security** for auth changes, **Performance** for data pipeline changes, **Historiography** for manuscript claims).

## Each agent runs

1. Read the issue exit criteria and the diff.
2. Evaluate the PR from its assigned perspective.
3. Return a structured verdict: **approve**, **comment**, or **request-changes**, with specific findings.

## Synthesis

After all agents return:

1. **Merge findings** — deduplicate, resolve contradictions (scope agent may flag what correctness agent requested).
2. **Run tests**: `make check` (lint-prose + pytest).
3. **Run build**: `make manuscript` (if prose changed).
4. **Check for stale info**: are STATE.md, ROADMAP.md, docs/* consistent with the changes?
5. **Post a single review**: `gh pr review <number> --comment --body "..."` or `--approve` / `--request-changes`. Attribute each finding to its perspective.

## What to look for (all perspectives)

- Does every changed file have a reason in the commit message?
- Are there new files that should be in .gitignore?
- Do commit messages explain *why*, not just *what*?
- Any secrets, large files, or conflict markers? (hook should catch, but verify)
- Any blacklisted AI-tell words introduced? (`make lint-prose`)
