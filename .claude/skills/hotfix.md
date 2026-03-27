# /hotfix — quick branch-merge cycle for a simple fix

Apply a small, self-contained fix through the full git cycle:
verify → branch → commit → push → merge → unbranch.

Use this for fixes that fit in one commit and don't need a ticket or PR review
(typos, one-liner bug fixes, config tweaks, STATE/ROADMAP housekeeping).
For anything larger, use the full Dreaming → Doing workflow.

## Usage

```
/hotfix <description of the fix>
```

The description is used to name the branch (`hotfix-<slug>`) and the commit message.

## Procedure

Run these steps in order. Stop and report on failure at any step.

### 1. Verify — clean working tree, tests pass

```bash
# Must be on main with no uncommitted changes
git status --porcelain
```

If the working tree is dirty, ask the user what to do. Then:

```bash
make check-fast
```

If tests fail, stop — the baseline is broken.

### 2. Branch

Derive a short kebab-case slug from the user's description (max 4 words).

```bash
git checkout -b hotfix-<slug>
```

### 3. Make the fix

Apply the change the user described. Keep it minimal — one logical change.

### 4. Verify again

```bash
make check-fast
```

If tests fail, fix or revert. Do not proceed with a red test suite.

### 5. Commit

Stage only the changed files (no `git add -A`). Commit message format:

```
fix: <what was fixed>

<Why this change and not another — one sentence.>
```

The pre-commit hook will enforce repo invariants (no main commits — but we're
on a branch, so this passes; no secrets; no large files; no conflict markers).

### 6. Push

```bash
git push -u origin hotfix-<slug>
```

Retry up to 4 times with exponential backoff on network failure.

### 7. Merge

Fast-forward merge into main (no merge commit for trivial fixes):

```bash
git checkout main
git merge --ff-only hotfix-<slug>
git push -u origin main
```

If fast-forward fails (main has diverged), rebase first:

```bash
git checkout hotfix-<slug>
git rebase main
git checkout main
git merge --ff-only hotfix-<slug>
git push -u origin main
```

### 8. Unbranch — clean up

```bash
git branch -d hotfix-<slug>
git push origin --delete hotfix-<slug>
```

### 9. Confirm

Report: branch name, commit hash, one-line summary of what changed.

## Guardrails

- **Scope**: if the fix touches more than 3 files or 30 lines, warn the user
  that this may deserve a ticket instead.
- **Tests**: `make check-fast` must pass both before and after the fix.
- **No skip**: never use `--no-verify` or `--force`.
- **Announce phase**: `[→ Doing]` at step 3, `[Doing → Celebrating]` at step 9.
