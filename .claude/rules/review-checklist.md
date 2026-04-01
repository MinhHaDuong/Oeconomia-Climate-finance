---
paths:
  - "scripts/**"
  - "config/**"
  - "content/**"
---

# PR review — doc propagation checklist (project-specific)

When `/review-pr` triggers doc propagation, trace references in these project files:
- `content/technical-report.qmd`
- `content/data-paper.qmd`
- `content/manuscript.qmd`
- `content/*-vars.yml`
- `docs/`
- `README.md`, `STATE.md`, `ROADMAP.md`
- `.claude/rules/architecture.md`
- config files

Also:
- On first review cycle, add a risk label to the PR:
  - Trivial → `review:trivial` (merge gate requires 1 cycle)
  - Standard or above → `review:standard` (merge gate requires 2 cycles)
- After build: run `make manuscript` if prose changed.
