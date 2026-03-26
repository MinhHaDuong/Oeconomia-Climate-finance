# Submission branch lifecycle

Manages a long-running branch that tracks a manuscript through submission,
review, revision, and acceptance at a specific journal.

## When to use

Create a submission branch when a paper is ready to submit. The branch
freezes the submitted state and accumulates revision history. Main
continues to evolve; the submission branch cherry-picks only what's
relevant to the paper under review.

## Branch naming

`submission/{journal}-{document}` — e.g., `submission/oeconomia-manuscript`,
`submission/rdj-data-paper`.

## Lifecycle

### 1. Sprout

**Gate**: run `.agent/runbooks/submission-readiness.md` checklist before proceeding.

#### Create the branch

```bash
git checkout -b submission/{journal}-{document} main
```

Verify the paper builds cleanly (use the actual target, e.g., `make output/content/manuscript.pdf`).

Tag the submission point:

```bash
git tag v{N}.0-{journal}-submitted
```

Add submission artifacts to `release/`:

- Cover letter
- AI disclosure statement
- Any journal-specific files (anonymized PDF, figures, metadata)
- Record in `release/release-journal.md`

Commit and push:

```bash
git add release/
git commit -m "release: submit {document} to {journal}"
git push -u origin submission/{journal}-{document}
```

### 2. Freeze

The submission branch is now frozen. Guards: pre-commit rejects merges (cherry-pick only), pre-push blocks deletion, GitHub branch protection prevents force-push. What was frozen:

- **Git tag** marks the exact submission commit
- **Pinned vars** in `content/{document}-vars.yml` (counts, percentages cited in prose)
- **Reference data** in `config/` (cluster labels, identifier lists, alluvial tables)
- **Reproducibility archives** on Zenodo (code + data tarballs, tested on two machines)

No changes on this branch except:

- Errata (errors discovered after submission)
- Reviewer responses
- Revision commits

Main continues to evolve independently.

### 3. Errata

If errors are discovered post-submission:

```bash
git checkout submission/{journal}-{document}
# Fix the error
git commit -m "errata: {description}"
```

Add errata materials to `release/YYYY-MM-DD {journal} errata/`.
Contact the journal editor if needed.

### 4. Revision

When reviewer reports arrive:

```bash
git checkout submission/{journal}-{document}
```

1. Add reviewer reports to `release/YYYY-MM-DD {journal} revision/`
2. Create a response document (`release/.../response-to-reviewers.md`)
3. Make changes on the submission branch, one commit per reviewer point
4. Tag the revision: `git tag v{N}.1-{journal}-revised`
5. If main has relevant improvements, cherry-pick them:
   ```bash
   git cherry-pick <commit-hash>  # specific fixes from main
   ```
   Do NOT merge main into the submission branch — it would pull in
   unrelated changes. (Enforced: pre-commit hook rejects merges on `submission/*` branches.)

### 5. Resubmission

After addressing all reviewer points:

1. Rebuild the paper (e.g., `make output/content/manuscript.pdf`)
2. Prepare a diff/track-changes document if required
3. Add resubmission artifacts to `release/`
4. Commit: `release: resubmit {document} to {journal} (revision 1)`
5. Push the branch

### 6. Acceptance

When the paper is accepted:

1. Tag: `git tag v{N}.{final}-{journal}-accepted`
2. Add acceptance letter to `release/`
3. Merge the submission branch back to main:
   ```bash
   git checkout main
   git merge --no-ff -m "Merge submission/{journal}-{document}: accepted" \
       submission/{journal}-{document}
   ```
   This brings revision improvements back to main.
4. Update `release/release-journal.md` with acceptance record
5. Update Zenodo deposit if needed (new version)

### 7. Rejection

If rejected:

1. Record the decision in `release/release-journal.md`
2. Decide: resubmit elsewhere (sprout a new submission branch from the
   current one) or abandon (leave the branch as historical record)
3. Cherry-pick any improvements worth keeping back to main

## Apply tickets

- **Oeconomia catch-up**: #376 (create branch from `v1.0-submission`, cherry-pick errata)
- **Data paper branch**: #421 (sprout `submission/rdj-data-paper` when ready)
