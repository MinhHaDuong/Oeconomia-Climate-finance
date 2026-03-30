# Revision Runbook: v1→v2 Workflow

Step-by-step procedures for handling reviewer-requested changes.

## 1. Revision branch workflow

```
main (live development)
  └── t{N}-revision-{journal}       (do the work, TDD applies)
        └── PR → main                (review)
              └── cherry-pick chain → submission/{journal}-{document}
                    └── tag: v{M}.{N+1}-{journal}-revised
```

**Rules:**
- Work happens on main via a ticket branch, not directly on the submission branch.
- Submission branch receives cherry-picks only (no merges — enforced by pre-commit hook).
- Each cherry-pick should build cleanly on the submission branch.

## 2. Version-stamped config

When analysis parameters change (e.g., K=6→8):

1. Copy current frozen config: `config/v1_*` → `config/v2_*`
2. Update the new config with revised parameters
3. Figure scripts that use frozen config get `--alluvial config/v2_*` etc.
4. `manuscript-vars.yml` stays pinned to v1; create `manuscript-vars-v2.yml` for revised numbers
5. Both versions coexist — needed for response letter comparisons

## 3. Scenario playbook

### A. Prose-only

Reviewer asks for text changes (framing, citations, wording).

1. Create ticket branch: `t{N}-prose-revision`
2. Edit `content/manuscript.qmd`
3. `make manuscript` to verify PDF builds clean
4. PR → main → cherry-pick to `submission/oeconomia-varia`
5. No config/figure changes needed

### B. Figure fix

Reviewer asks for label correction, color change, axis adjustment.

1. Create ticket branch: `t{N}-fix-figure-{name}`
2. Fix the figure script
3. `make figures-manuscript` to regenerate
4. If output changed: freeze new `config/v2_*` files
5. PR → main → cherry-pick chain (script fix, then regenerated output)

### C. Parameter change

Reviewer asks to rerun with different parameters (e.g., K=8, different cite_threshold).

1. Create ticket branch: `t{N}-param-{param}-{value}`
2. Update `config/analysis.yaml` (e.g., `k: 8`)
3. `make figures` (if Phase 2 only) or `dvc repro && make figures` (if Phase 1 changed)
4. Freeze new outputs: `cp content/tables/tab_alluvial.csv config/v2_tab_alluvial.csv`
5. Regenerate figures: `make figures`
6. Update manuscript text (cluster descriptions, numbers)
7. Update `manuscript-vars-v2.yml` if computed stats changed
8. PR → main → cherry-pick chain to submission branch

**Cherry-pick order:**
1. Config changes first
2. Script changes second
3. Regenerated outputs third (figures, tables, vars)
4. Manuscript text last
5. Tag after all cherry-picks land

### D. Corpus expansion

Reviewer asks to include 2025 data or additional sources.

1. Create ticket branch: `t{N}-corpus-expansion-{description}`
2. Update `config/corpus_collect.yaml` (year_max, new queries)
3. Run full pipeline: `make corpus` (on padme — GPU, API access)
4. Verify: `make corpus-validate` (acceptance tests)
5. Freeze new v2 config: `config/v2_*`
6. Regenerate all figures: `make figures`
7. Update manuscript numbers from `manuscript-vars-v2.yml`
8. Update data paper if corpus stats changed significantly
9. PR → main → cherry-pick chain
10. New Zenodo version (see §6)

### E. Methodological change

Reviewer asks for different embedding model, clustering algorithm, or analysis approach.

1. Create ticket branch: `t{N}-method-{description}`
2. Modify analysis script(s)
3. Rerun affected pipeline stages
4. Compare v1/v2 outputs (side-by-side figures)
5. Update manuscript and technical report
6. PR → main → cherry-pick chain
7. Document in response letter why the change was made

## 4. Response letter template

```markdown
# Response to Reviewers — [Journal] [Date]

We thank the reviewers for their careful reading and constructive feedback.
Changes are highlighted in the revised manuscript. Below we address each
comment individually.

## Reviewer 1

### Comment 1.1: [summary in own words]

> [exact quote from review]

**Response**: [what we did and why]

**Evidence**: [diff reference, figure comparison, or new analysis]

**Location**: §[section] p.[page] in revised manuscript

---

### Comment 1.2: ...

## Reviewer 2

### Comment 2.1: ...
```

## 5. Side-by-side figure comparison

For the response letter, compare v1 and v2 figures:

```bash
# Manual comparison (ImageMagick):
montage v1_fig_bars.png v2_fig_bars.png -tile 2x1 -geometry +10+10 \
    release/revision-diff/fig_bars_comparison.png

# Or: open both in an image viewer
```

A `make revision-diff` target can be added once the first real revision happens.
For now, keep it manual — automate after knowing which figures actually change.

## 6. Zenodo revision checklist

When creating a new Zenodo version for a revised submission:

- [ ] New version on existing Zenodo record (not a new record)
- [ ] Upload revised manuscript PDF
- [ ] Upload revised reproducibility archive (`make archive-datapaper`)
- [ ] Update metadata: version number, revision date, changelog
- [ ] Update the "Related identifiers" if HAL version changed
- [ ] Reserve DOI before uploading (if needed for cross-references)
- [ ] Update `STATE.md` with new Zenodo DOI and version tag
- [ ] Tag in git: `v{M}.{N+1}-{journal}-revised`

## 7. Post-revision cleanup

After the submission branch is updated and tagged:

1. Update `STATE.md`: new version, new tag, new DOI
2. Update `ROADMAP.md` if milestones changed
3. Close the ticket
4. Delete the ticket branch (keep the submission branch)
5. `/celebrate`
