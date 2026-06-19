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

**Source vs records.** The branch freezes the manuscript *source* (qmd, pinned vars, reference data) and its revision history — git's job. Submission *records* (cover/decision letters, frozen PDFs, deposit archives, reviewer reports, response letters) live outside the repo in `papiers/<state>/<track>/`, where `<state>` ∈ {actif, sent, published} and `<track>` is the venue-named record dir (e.g. `papiers/actif/Oeconomia_Inventing_Climate_Finance/`). State transitions are a plain `mv` between `papiers/{actif,sent,published}/`. Records are not git-tracked.

## Branch naming

`submission/{journal}-{document}` — e.g., `submission/oeconomia-manuscript`.

## 1. Sprout

**Gate**: run `/submission-readiness` checklist first.

```bash
git checkout -b submission/$0-$1 main
# Verify build: make output/content/$1.pdf
git tag v{N}.0-$0-submitted
```

Place records (cover letter, AI disclosure, journal-specific files) in `papiers/<state>/<track>/` (outside the repo — not git-tracked). On the branch, commit only the source freeze (pinned vars, reference data) and push. Enable branch protection.

## 2. Freeze

Branch is frozen. Guards: pre-commit rejects merges (cherry-pick only), pre-push blocks deletion, GitHub prevents force-push.

Frozen: git tag, pinned vars in `content/{document}-vars.yml`, reference data in `config/`, Zenodo archives.

No changes except errata, reviewer responses, and revision commits.

## 3. Errata

Fix errors post-submission. Add errata materials to `papiers/<state>/<track>/YYYY-MM-DD {journal} errata/`. Contact editor if needed.

## 4. Revision

When reviewer reports arrive:
1. Add reports to `papiers/<state>/<track>/YYYY-MM-DD {journal} revision/`
2. Create response document
3. One commit per reviewer point
4. Tag: `v{N}.1-{journal}-revised`
5. Cherry-pick relevant improvements from main (never merge)

## 5. Resubmission

Rebuild, prepare diff/track-changes, add records to `papiers/<state>/<track>/`; commit the source changes on the branch and push.

## 6. Acceptance

Tag `v{N}.{final}-{journal}-accepted`. Add the acceptance letter to the track record and `mv` the track dir `papiers/sent/<track>/` → `papiers/published/<track>/`. Merge submission branch back to main. Update Zenodo.

## 7. Rejection

Record decision. Decide: resubmit elsewhere (new submission branch) or abandon (leave as record). Cherry-pick improvements back to main.
