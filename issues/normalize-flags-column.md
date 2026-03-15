# Stop persisting derived `flags` column in `extended_works.csv`

## Problem

The `flags` column in `extended_works.csv` is a derived list built by `merge_flags()` from 6 individual boolean columns that live in the same file. Persisting it:

- **Duplicates information** — the booleans are the source of truth
- **Creates consistency risk** — add a 7th flag and every reconstruction site must update
- **Causes defensive code** — three separate reconstruction guards exist because the stored value goes stale or changes format (list vs string)

## Current state

### Persisted in two files

| File | Format | Verdict |
|------|--------|--------|
| `extended_works.csv` | stringified Python list | **Remove** — booleans in same file |
| `corpus_audit.csv` | pipe-delimited string | **Keep** — human-readable audit artifact |

### Three reconstruction guards (code smell)

1. `apply_filter()` lines 203–213: re-parses or re-merges if column missing or stringified
2. `save_extended()` line 250: rebuilds if absent
3. `run_flagging()` line 373: always rebuilds from booleans

### Five consumption sites in `corpus_refine.py`

| Site | Lines | Current pattern | Replacement |
|------|-------|----------------|-------------|
| Filtering | 216 | `flags.apply(len) > 0` | `df[FLAG_COLUMNS].any(axis=1)` |
| Summary | 158–178 | iterate flag lists | iterate boolean columns |
| Audit write | 228 | serialize list to pipe-string | build pipe-string from booleans at write time |
| Dry-run audit | 266 | same serialization | same fix |
| Blacklist verify | 131 | check flag contents | check `title_blacklist` boolean directly |

### Test fixtures

- `test_split_corpus_refine.py:189` — creates fixture with `flags` as JSON string; switch to boolean columns
- `test_corpus_acceptance.py` — reads `flags` from `corpus_audit.csv` (legitimate; no change needed)

## Definition of done

- [ ] `flags` column no longer written to `extended_works.csv`
- [ ] All filtering/summary logic in `corpus_refine.py` uses boolean columns directly
- [ ] `flags` pipe-string still written to `corpus_audit.csv`, built from booleans at write time
- [ ] Three reconstruction guards deleted
- [ ] `merge_flags()` either deleted or reduced to audit-serialization helper
- [ ] Test fixtures updated to use boolean columns
- [ ] `make clean && make all` passes
- [ ] `uv run pytest` passes

## Design note

**Store the atoms, derive the molecules.** The boolean columns are the atoms (expensive, some non-deterministic). The `flags` list is a molecule — cheap, deterministic, and should be computed at point of use.
