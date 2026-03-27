---
name: submission-branch
description: Manage submission branch lifecycle — sprout, freeze, errata, revision, resubmission, acceptance.
disable-model-invocation: true
user-invocable: true
argument-hint: <journal> <document>
---

# Submission branch lifecycle

Manages a long-running branch tracking a manuscript through submission, review, revision, and acceptance.

## When to use

Create when a paper is ready to submit. The branch freezes the submitted state and accumulates revision history. Main continues to evolve; the submission branch cherry-picks only what's relevant.

## Branch naming

`submission/{journal}-{document}` — e.g., `submission/oeconomia-manuscript`.

## 1. Sprout

**Gate**: run `/submission-readiness` checklist first.

```bash
git checkout -b submission/$0-$1 main
# Verify build: make output/content/$1.pdf
git tag v{N}.0-$0-submitted
```

Add to `release/`: cover letter, AI disclosure, journal-specific files. Commit and push. Enable branch protection.

## 2. Freeze

Branch is frozen. Guards: pre-commit rejects merges (cherry-pick only), pre-push blocks deletion, GitHub prevents force-push.

Frozen: git tag, pinned vars in `content/{document}-vars.yml`, reference data in `config/`, Zenodo archives.

No changes except errata, reviewer responses, and revision commits.

## 3. Errata

Fix errors post-submission. Add to `release/YYYY-MM-DD {journal} errata/`. Contact editor if needed.

## 4. Revision

When reviewer reports arrive:
1. Add reports to `release/YYYY-MM-DD {journal} revision/`
2. Create response document
3. One commit per reviewer point
4. Tag: `v{N}.1-{journal}-revised`
5. Cherry-pick relevant improvements from main (never merge)

## 5. Resubmission

Rebuild, prepare diff/track-changes, add to `release/`, commit, push.

## 6. Acceptance

Tag `v{N}.{final}-{journal}-accepted`. Add acceptance letter. Merge submission branch back to main. Update Zenodo.

## 7. Rejection

Record decision. Decide: resubmit elsewhere (new submission branch) or abandon (leave as record). Cherry-pick improvements back to main.
