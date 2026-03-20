# Brain dump: Extract harness into its own repo

Date: 2026-03-19

**Status (2026-03-20):** Implementation started. Contents transferred to
[MinhHaDuong/agentic-harness](https://github.com/MinhHaDuong/agentic-harness)
(`docs/braindump-harness-extraction.md`). Telemetry is the first module.
Git history of this file has the full original text.

## Ideas transferred

1. Split the harness into its own repo → **done** (`agentic-harness`)
2. Review harness against seminal SE books → transferred
3. Offline ticket system (file-based, gh-optional) → transferred
4. Skill-based agent coordination → transferred
5. Background ticket poller → transferred
6. Type assertion guidelines → transferred
7. Script hygiene defaults → transferred
8. Sweep disk for reusable guidelines → transferred

## Codebase review findings (2026-03-19)

Oeconomia-specific — stays here, not in agentic-harness.
Audit of the pipeline (63 scripts, ~19k lines) to inform harness defaults.

**Works well:** Zero classes, no security smells, consistent `get_logger()`, f-strings dominant.

**Remaining issues:**
1. `utils.py` is 717-line god module (logging, retries, paths, checkpointing)
2. Plotting scripts have 200-400 line functions
3. Hardcoded constants across 20+ scripts

| Metric | Value |
|--------|-------|
| Total scripts | 68 (63 + 5 archive_traditions) |
| Average length | ~308 lines |
| Longest | `collect_syllabi.py` (855 lines) |
| Classes | 0 |
| Functions >50 statements (ruff PLR0915) | 22 |
| Test files | 27 |
