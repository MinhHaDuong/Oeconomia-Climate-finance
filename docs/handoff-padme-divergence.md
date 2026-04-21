# Handoff: divergence pipeline → padme

**Date:** 2026-04-15
**Branch:** `claude/structural-change-detection-Js5Y2`
**Status:** Code complete, tested on 100-row smoke fixture. Needs real data run.

## What was done

Multi-channel structural break detection pipeline: 15 continuous divergence
methods (5 semantic, 3 lexical, 8 citation graph), 3 change point detectors
(PELT, Dynp, KernelCPD), embedding insensitivity analysis (PCA + JL),
convergence analysis across channels.

Architecture: 1-script-1-output, Pandera schema validation, modular
Makefile (`divergence.mk`), configurable seeds, shared I/O module.

77 tests (27 fast / 50 slow), 15 golden value regression tests.

## Steps on padme

### 1. Sync and install

```bash
git fetch origin claude/structural-change-detection-Js5Y2
git checkout claude/structural-change-detection-Js5Y2
uv sync --extra cu130
# New deps added to pyproject.toml:
pip install pot dcor ruptures   # or uv pip install
```

### 2. Verify tests pass

```bash
make check-fast                  # or: pytest -m "not slow" (< 15s)
pytest tests/test_divergence.py tests/test_changepoints.py \
       tests/test_embedding_sensitivity.py tests/test_golden_values.py
```

### 3. Run the pipeline on real data

```bash
# All 15 divergence methods (parallelizable):
make -j4 divergence-tables       # ~20 min CPU, ~5 min if GPU ticket done

# Null model (permutation Z-scores) — GPU + joblib accelerated (PR #702, #705):
# Wall-clock is dominated by G2_spectral; scales roughly with NJOBS / 24.
make null-model                  # NJOBS=-1 (all cores), ~2-3 min on padme
                                 # S2 ~8s (GPU), G9 ~40s, L1 ~90s, G2 ~60s at n_jobs=24
# Under `make -jN`, cap per-method parallelism to avoid oversubscription:
make -j4 NJOBS=6 null-model      # 24-core box, 4 methods × 6 workers, ~10 min
                                 # (G2 drops to ~10 min at n_jobs=6, dominates)

# Change point detection + convergence:
make changepoints

# Embedding sensitivity (PCA + JL for S1_MMD, S2_energy):
make sensitivity

# All at once:
make divergence
```

### 4. Inspect results

```bash
# Quick look at convergence:
python3 -c "
import pandas as pd
df = pd.read_csv('content/tables/tab_changepoints_convergence.csv')
print(df.nlargest(10, 'pct_total')[['year','pct_total','methods_detecting']])
"

# Generate figures:
make divergence-figures
make changepoints-figure
make sensitivity-figures
```

### 5. Compare with old results

```bash
# Old pipeline (KMeans k=6 + JS):
python3 scripts/compute_breakpoints.py --output /tmp/old_breaks.csv
# New pipeline: content/tables/tab_changepoints_convergence.csv
# Do the same years appear? Is 2007/2013 confirmed or an artifact?
```

## Open tickets (padme-dependent)

| Ticket | What | Priority |
|--------|------|----------|
| **0037** | GPU acceleration (torch backend for S1-S4) | High — 4× speedup |
| **0041** | Profile pipeline on real data, document timings | High — need actual numbers |
| **0042** | Run on real corpus, review results | **Critical** — the actual science |
| 0035 | Validation corpora (ISTEX for known-break fields) | Medium |
| 0034 | Write structural-breaks-v2 include (needs 0042 results) | After 0042 |
| 0040 | Wire results into technical report | After 0034 |
| S5 | Procrustes word embeddings (train per-period word2vec) | Low |

**Critical path: 0037 → 0042 → 0034 → 0040**

## Key files

```
scripts/
  compute_divergence.py          # dispatch: --method S1_MMD
  _divergence_semantic.py        # S1-S4 implementations
  _divergence_lexical.py         # L1-L3
  _divergence_citation.py        # G1-G8
  _divergence_io.py              # shared I/O helpers
  compute_changepoints.py        # PELT + Dynp + KernelCPD
  compute_convergence.py         # cross-method agreement
  compute_embedding_sensitivity.py  # PCA + JL
  plot_divergence.py             # --aggregate {none,ribbon} --palette {auto,gradient}
  plot_convergence.py            # heatmap + stacked bars
  schemas.py                     # DivergenceSchema (Pandera)
config/analysis.yaml             # all parameters (divergence section)
divergence.mk                   # Make targets
docs/literature-review-structural-break-detection.md
```

## What to watch for on real data

1. **MMD / energy distance runtime.** Subsampled to 2000 per side, but
   verify wall-clock time. If > 10s per (year, window), consider GPU (0037).
   Null-model path already uses GPU auto-detection for S2/S1 (PR #702) and
   joblib parallelism for G2/G9 (PR #705) — see `scripts/_permutation_accel.py`.
2. **Citation graph methods.** Smoke fixture has 0 internal edges → G1,G2,
   G4-G6,G8 produce NaN. Real corpus should have thousands of internal edges.
   If still sparse, investigate citation coverage.
3. **G7 disruption proxy.** Check hyperparams column — if `mode=proxy`
   appears on real data, the internal edge count is too low for true CD.
4. **Convergence.** If semantic, lexical, AND citation channels agree on a
   break year → robust. If only one channel detects it → method artifact.
5. **Embedding sensitivity.** PCA dims 32-512 should produce similar break
   dates. If d=32 disagrees with d=512, the breaks depend on fine structure.
