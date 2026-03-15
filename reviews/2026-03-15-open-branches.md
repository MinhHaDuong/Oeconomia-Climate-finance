# Review of open branches — 2026-03-15

Reviewer: Claude (fresh-context review, no shared history with implementing agents)

Updated after second pass (same session).

---

## Status summary

| Branch | Commits | Verdict | Action |
|---|---|---|---|
| `claude/normalize-data-model-O72d8` | 4 | **Approve** | Ready to merge |
| `claude/review-agents-documentation-kLQvH` | 4 | **Comment** | Author input needed |
| `t121-fix-timeout-truncation` | 1 | ~~Approve~~ | **MERGED** ✓ |
| `t118-mark-slow-tests` | — | — | **MERGED** ✓ |
| `t119-check-fast` | 1 | **Block** | Do not merge — stale, would revert fixes |
| `claude/define-data-pipeline-7wskr` | 1 | **Comment** | Run-once script, not for merge |
| `claude/document-reasoning-levels-BLW53` | 3 | **Block** | 72 commits behind main, must rebase |

---

## 1. `claude/normalize-data-model-O72d8` — Stop persisting derived `flags` column

**4 commits** (ticket → red test → green impl → gitignore fix) | **Verdict: Approve**

### Summary

Removes the derived `flags` list column from `extended_works.csv`. Boolean flag columns are
the source of truth; the `flags` list is now only serialized as a pipe-delimited string in
`corpus_audit.csv`. Three reconstruction guards eliminated.

### Findings

| Perspective | Confidence | Finding |
|---|---|---|
| Correctness | High | Logic correct. `df[flag_cols].fillna(False).any(axis=1)` properly replaces `flags.apply(len) > 0` across all 5 consumption sites. |
| Consistency | Medium | `_serialize_flags_pipe()` docstring mentions "detail suffixes" but those are computed in `merge_flags()`, not in the wrapper. Minor doc mismatch — acceptable. |
| Scope | High | DVC lock + run_reports hash changes from pipeline re-run are expected. `.gitignore` addition for checkpoint file has its own commit. |

### TDD quality

Excellent. The git log tells the story: intent (ticket) → contract (failing test) → solution
(implementation) → cleanup (gitignore). Each commit self-contained.

---

## 2. `claude/review-agents-documentation-kLQvH` — Rewrite review-pr runbook + extract housekeeping/memory

**4 commits** | **Verdict: Comment — needs author input on two questions**

### Summary

- Extracts housekeeping triggers and memory policy from AGENTS.md into `runbooks/housekeeping.md`
  and `runbooks/memory.md`
- Rewrites `review-pr.md` to require multi-perspective agent reviews with proportional depth
- Adds code-quality escalation policy

### Findings

| Perspective | Confidence | Finding |
|---|---|---|
| Correctness | High | Extracted runbooks faithfully reproduce original content. No information lost. |
| Scope | High | Multi-agent review framework assumes parallel agent worktrees and structured verdicts. Is this documenting current capability or target state? |
| Consistency | Medium | Agents that auto-load AGENTS.md previously found memory path (`$CLAUDE_MEMORY_DIR/MEMORY.md`) inline. Now they must also read `runbooks/memory.md`. Could cause silent regression in memory behavior. |
| Red team | Medium | The review-pr runbook is now 80+ lines. Is this proportional to this project's PR volume? |

### Questions for author

1. **Memory path discovery**: Is it acceptable that `$CLAUDE_MEMORY_DIR/MEMORY.md` is no longer
   mentioned in AGENTS.md itself? Some agents may not read runbooks unless told to.
2. **Aspirational vs. operational**: Should the runbook note which parts are aspirational?

---

## 3. `t121-fix-timeout-truncation` — MERGED ✓

Merged as `4d9ffba Merge t121-fix-timeout-truncation: remove int() cast on request_timeout`.

---

## 4. `t118-mark-slow-tests` — MERGED ✓

Merged as `e51f27b Merge t118-mark-slow-tests: pytest-timeout + make check-fast`.

---

## 5. `t119-check-fast` — DO NOT MERGE

**1 commit** by author (Minh Ha-Duong) | **Verdict: Close this branch**

### Why it cannot be merged

The branch was created from `283bedf` (before DOI dedup #120 and timeout fix #121). Merging
it would **revert** both of those already-merged fixes:

- Removes DOI dedup logic from `apply_filter()` (reverts #120)
- Re-introduces `int(request_timeout)` cast at 3 sites (reverts #121)
- Removes `pytest-timeout` dependency and `deduped` from valid audit actions

### What it contains that's valid

The author's version of `make check-fast` differs slightly from the agent's:
- Removes `pytest-timeout` dependency (reasonable simplification — timeouts not actually
  enforced, just marked)
- Slightly different slow-marker docstring
- Cleaner module-level `pytestmark` pattern

### Recommendation

The `make check-fast` feature is already in main via `t118`. The `pytest-timeout` removal
(if desired) should be a new ticket branched from current main, not this branch.

---

## 6. `claude/define-data-pipeline-7wskr` — Run-once utility, not for merge

**1 commit** | **Verdict: Use locally, then delete branch**

### What it is

Adds `scripts/create_dvc_review_issues.sh` — a bash script that calls `gh issue create`
6 times to open issues identified during the DVC code review (#101–#104).

### Problems with merging

- Branch is **10 commits behind main** (created from `f95a6ac`, before DVC integration, DOI
  dedup, timeout fix). The diff vs main shows it would remove `.dvc/` config and DVC docs from
  README — those are not the script's changes, just stale merge conflicts.
- The script is meant to be run once then deleted (commit message says: "delete the script").
  It does not belong in git history.

### Recommendation

Run the script locally from a `gh`-authenticated machine, then close the branch. If the
6 issues are already created, just close the branch.

---

## 7. `claude/document-reasoning-levels-BLW53` — Must rebase before review

**3 commits** | **Verdict: Block — rebase required**

### What the commits do

1. `aee61d9` docs: document two reasoning levels in git messages
2. `0990ac4` Add organized forgetting policy for AGENTS.md Status
3. `29003e8` Add Definition of Done requirement for tickets

These are substantive improvements to AGENTS.md:
- Formalizes commit message / merge commit as two distinct reasoning levels
- Introduces "organized forgetting" for Status (Dimensions / Open fronts / Next, each with
  a defined lifetime)
- Requires Definition of Done before starting any ticket

### Why it cannot be merged as-is

Branch diverged from `da0e447` — **72 commits behind main**. At that point, AGENTS.md was
a completely different document (135 lines, different structure). The 3 commits were applied
to that old AGENTS.md. Merging would replace the current 135-line procedural AGENTS.md with
a 338-line content-focused rewrite that predates all the recent workflow improvements.

### Recommendation

The 3 conceptual additions are valuable. Rebase the branch onto current main and re-apply
the 3 changes to the current AGENTS.md structure. The ideas map cleanly:
- "Reasoning levels" → add under `## Git discipline`
- "Organized forgetting" → update the housekeeping section (or `runbooks/housekeeping.md`
  if PR #2 merges first)
- "Definition of Done" → add under `## GitHub Issues as plans`
