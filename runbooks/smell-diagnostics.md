## Context

The test harness (`tests/test_script_hygiene.py`) has two-tier thresholds
(smell/wall) for complexity and module length. The wall tests hard-fail;
the smell tests emit warnings. But the warnings are bare numbers:
"scripts exceed 500 lines" or "C901 complexity > 15". An agent reading
this output gets a *target to beat*, not *understanding of what's wrong*.

This leads to line-count-driven refactoring: shaving comments, collapsing
blank lines, extracting trivially small helpers — changes that reduce a
number without improving readability.

The harness needs a **diagnostic layer** between "detect smell" and
"report number". When a smell fires, the warning should explain *what
kind* of problem it is and *what refactoring pattern* fits. The agent
(or human) then acts on understanding, not arithmetic.

## Relevant files

- `tests/test_script_hygiene.py` — the harness, smell/wall tests
- `docs/coding-guidelines.md` — § Script hygiene (the "why" behind each check)

## Actions

### 1. Define smell categories with diagnostic messages

For each smell type, map the ruff output to a human-readable diagnosis:

**C901 (complexity):**
- High branching (many if/elif) → "Consider lookup table or dispatch dict"
- Deep nesting (nested loops/conditions) → "Extract inner block into named helper"
- Mixed concerns (I/O + logic + error handling) → "Separate orchestration from computation"

**PLR0915 (too many statements):**
- Sequential pipeline (load → transform → save) → "Extract phases into named steps"
- Argparse-heavy (20+ arguments) → "Group related args, consider config file"
- Mixed logging/progress interleaved with logic → "Separate progress reporting"

**PLR0912 (too many branches):**
- Type-dispatch chain (if type == "A" / elif type == "B" / ...) → "Use dict dispatch or match/case"
- Error-handling fan-out (try/except per case) → "Extract error-handling wrapper"
- Validation cascade (check A, check B, check C) → "Extract validator functions"

**Module length (>500 lines):**
- Multiple unrelated responsibilities → "Split into focused modules"
- Large data constants (prompt templates, URL lists) → "Extract to config module"
- Visualization mixed with analysis → "Separate plotting into plot_<name>.py"

### 2. Implement diagnostic introspection

For each smell violation, run lightweight AST analysis to classify *why*
the function is complex, not just *how much*. Approaches:

- **Branch type**: parse the AST to count if/elif chains vs nested ifs vs
  try/except blocks. A function with 20 elif branches has a different fix
  than one with 5 nested loops.
- **Statement composition**: classify statements as I/O, computation,
  logging, argparse setup. A function that's 40% argparse has a different
  fix than one that's 40% business logic.
- **Module structure**: for length smells, count top-level def/class nodes
  and their sizes. A file with 3 big functions needs splitting differently
  than one with 30 small functions.

### 3. Enrich warning output

Change smell test warnings from:
```
UserWarning: 10 scripts exceed 500 lines (consider splitting):
analyze_bimodality.py (673L), ...
```

To:
```
UserWarning: Module length smells (>500 lines):
  analyze_bimodality.py (673L) — analysis + visualization mixed (12 plot functions, 8 analysis functions)
  analyze_genealogy.py (798L) — analysis + visualization mixed (9 plot functions, 11 analysis functions)
  utils.py (717L) — multiple responsibilities (HTTP retry, config loading, data I/O, normalization)
  collect_syllabi.py (855L) — large data constants (4 prompt/URL lists = 134 lines)
```

And for function complexity:
```
UserWarning: C901 smells (complexity > 15):
  catalog_grey.py:_query_worldbank_single (C901=21) — deep nesting: 4-level if/try/for/if → extract inner loop body
  qa_detect_type.py:classify_type (C901=31) — 19-branch elif chain → use dispatch table
  build_het_core.py:main (C901=23) — sequential pipeline with inline error handling → extract named steps
```

### 4. Keep it maintainable

The diagnostic logic should be:
- Heuristic, not perfect — a wrong classification is better than no classification
- Separate from the pass/fail logic — diagnostics are advisory
- In a helper function, not inline in each test
- Tested: add a few unit tests for the classifier (e.g., "a function with
  15 elif branches should be classified as 'type-dispatch chain'")

## Test

First test (red step):
```python
def test_smell_diagnostic_includes_pattern():
    """Smell warnings must include a refactoring pattern hint."""
    # Run the smell tests, capture warnings
    # Assert each warning line contains a pattern like "→ ..." or "—"
    # that describes the kind of problem, not just the number
```

## Verification

- [ ] `uv run pytest tests/test_script_hygiene.py -v -W all` shows enriched warnings
- [ ] Each smell warning includes: filename, metric, diagnosis, suggested pattern
- [ ] Wall tests (hard fail) are unchanged — diagnostics are smell-only
- [ ] No new dependencies (AST analysis uses stdlib `ast` module)
- [ ] `make check-fast` passes

## Invariants

- Wall test behavior unchanged (same thresholds, same pass/fail)
- No changes to scripts/ — this is harness-only
- No new external dependencies

## Exit criteria

- Every smell warning includes a heuristic diagnosis (what kind of problem)
  and a suggested refactoring pattern (what to do about it)
- At least 3 diagnostic categories per smell type (C901, PLR0915, PLR0912, module length)
- Unit tests for the diagnostic classifier
