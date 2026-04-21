"""Pandera schemas for pipeline contract files.

Declares the expected shape of:
- refined_works.csv — corpus metadata (Phase 1→2 contract)
- refined_citations.csv — citation edges (Phase 1→2 contract)
- refined_embeddings.npz — embedding vectors (validated via function)
- DivergenceSchema — per-method divergence CSV (Phase 2 internal contract)
- BootstrapSchema — bootstrap replicates CSV (ticket 0047)
- DivergenceSummarySchema — summary table joining point/boot/null (ticket 0047)

Used by:
- corpus_align.py (writer side): validate before writing
- pipeline_loaders.py (reader side): validate on load
- compute_divergence.py: validate divergence output
- compute_divergence_bootstrap.py: validate bootstrap output
- export_divergence_summary.py: validate summary output
- tests/test_schema_contracts.py, tests/test_divergence.py, tests/test_bootstrap.py
"""

import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema

# ---------------------------------------------------------------------------
# refined_works.csv
# ---------------------------------------------------------------------------

# All columns read as str (dtype=str, keep_default_na=False convention).
# Numeric columns are coerced after loading, not at schema level.
RefinedWorksSchema = DataFrameSchema(
    columns={
        "source": Column(str),
        "source_id": Column(str),
        "doi": Column(str, nullable=True),
        "title": Column(str, nullable=True),
        "first_author": Column(str, nullable=True),
        "all_authors": Column(str, nullable=True),
        "year": Column(str),
        "journal": Column(str, nullable=True),
        "abstract": Column(str, nullable=True),
        "language": Column(str, nullable=True),
        "keywords": Column(str, nullable=True),
        "categories": Column(str, nullable=True),
        "cited_by_count": Column(str, nullable=True),
        "affiliations": Column(str, nullable=True),
        # Source provenance booleans (stored as str "0"/"1"/"True"/"False")
        "from_openalex": Column(str, nullable=True),
        "from_istex": Column(str, nullable=True),
        "from_bibcnrs": Column(str, nullable=True),
        "from_scispace": Column(str, nullable=True),
        "from_grey": Column(str, nullable=True),
        "from_teaching": Column(str, nullable=True),
        "source_count": Column(str, nullable=True),
        "abstract_status": Column(str, nullable=True),
        "near_duplicate_group": Column(str, nullable=True),
        "in_v1": Column(str, nullable=True),
    },
    strict=False,  # allow extra columns (forward-compatible)
    coerce=False,  # we read as str, no coercion
)

# ---------------------------------------------------------------------------
# refined_citations.csv
# ---------------------------------------------------------------------------

RefinedCitationsSchema = DataFrameSchema(
    columns={
        "source_doi": Column(str),
        "source_id": Column(str, nullable=True),
        "ref_doi": Column(str, nullable=True),
        "ref_title": Column(str, nullable=True),
        "ref_first_author": Column(str, nullable=True),
        "ref_year": Column(str, nullable=True),
        "ref_journal": Column(str, nullable=True),
        "ref_raw": Column(str, nullable=True),
    },
    strict=False,
    coerce=False,
)

# ---------------------------------------------------------------------------
# Divergence series CSV (Phase 2 internal contract)
# ---------------------------------------------------------------------------

DivergenceSchema = DataFrameSchema(
    columns={
        "year": Column(int),
        "channel": Column(
            str, checks=pa.Check.isin(["semantic", "lexical", "citation"])
        ),
        # window is always str: sliding methods store "2", "3", etc.;
        # cumulative citation methods store "cumulative".
        # Writers must use str(w) to avoid mixed int/str in the same CSV.
        "window": Column(str),
        "hyperparams": Column(str, nullable=True),
        "value": Column(float, nullable=True),
    },
    strict=True,  # no extra columns allowed
    coerce=True,  # coerce types on validation
)

# ---------------------------------------------------------------------------
# C2ST divergence CSV (ticket 0068)
# ---------------------------------------------------------------------------
#
# C2ST methods (C2ST_embedding, C2ST_lexical) report AUC with per-fold CV
# variance as their inference primitive, NOT a permutation null. The extra
# columns carry the K fold scores summarised as std, Student-t CI bounds,
# and a one-sample t-test p-value against chance (0.5). Downstream plots /
# summaries read these columns directly instead of joining a tab_null_*.csv.

C2STDivergenceSchema = DataFrameSchema(
    columns={
        "year": Column(int),
        "channel": Column(str, checks=pa.Check.isin(["semantic", "lexical"])),
        "window": Column(str),
        "hyperparams": Column(str, nullable=True),
        "value": Column(float, nullable=True),  # AUC mean over folds
        "auc_std": Column(float, nullable=True),
        "auc_q025": Column(float, nullable=True),
        "auc_q975": Column(float, nullable=True),
        "n_folds": Column(int, nullable=True),
        "p_value_vs_chance": Column(float, nullable=True),
    },
    strict=True,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Null model CSV (permutation Z-scores, ticket 0055)
# ---------------------------------------------------------------------------

NullModelSchema = DataFrameSchema(
    columns={
        "year": Column(int),
        "window": Column(str),
        "observed": Column(float, nullable=True),
        "null_mean": Column(float, nullable=True),
        "null_std": Column(float, nullable=True),
        "z_score": Column(float, nullable=True),
        "p_value": Column(float, nullable=True),
    },
    strict=True,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Bootstrap replicates CSV (ticket 0047)
# ---------------------------------------------------------------------------

BootstrapSchema = DataFrameSchema(
    columns={
        "method": Column(str),
        "year": Column(int),
        "window": Column(str),
        "hyperparams": Column(str, nullable=True),
        "replicate": Column(int),
        "value": Column(float, nullable=True),
    },
    strict=True,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Divergence summary CSV (ticket 0047)
# ---------------------------------------------------------------------------

DivergenceSummarySchema = DataFrameSchema(
    columns={
        "method": Column(str),
        "year": Column(int),
        "window": Column(str),
        "hyperparams": Column(str, nullable=True),
        "point_estimate": Column(float, nullable=True),
        "boot_median": Column(float, nullable=True),
        "boot_q025": Column(float, nullable=True),
        "boot_q975": Column(float, nullable=True),
        "z_score": Column(float, nullable=True),
        "p_value": Column(float, nullable=True),
        "significant": Column(bool),
    },
    strict=True,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Interpretation CSV (discriminative terms, ticket 0056)
# ---------------------------------------------------------------------------

InterpretationSchema = DataFrameSchema(
    columns={
        "term": Column(str),
        "log_odds": Column(float),
        "freq_before": Column(int),
        "freq_after": Column(int),
    },
    strict=True,
    coerce=True,
)

# ---------------------------------------------------------------------------
# Cross-year Z-score CSV (zoo methods, explore-zoo-report)
# ---------------------------------------------------------------------------

CrossyearZscoreSchema = DataFrameSchema(
    columns={
        "method": Column(str),
        "year": Column(int),
        "window": Column(str),
        "value": Column(float, nullable=True),
        "z_score": Column(float, nullable=True),
    },
    strict=True,
    coerce=True,
)

# ---------------------------------------------------------------------------
# refined_embeddings.npz
# ---------------------------------------------------------------------------


def validate_refined_embeddings(vectors, n_works):
    """Validate embedding vectors are aligned with refined_works.csv.

    Parameters
    ----------
    vectors : np.ndarray
        Shape (N, D) float32 array.
    n_works : int
        Expected number of rows (from refined_works.csv).

    Raises
    ------
    ValueError
        If row count doesn't match or dimensions are wrong.

    """
    if vectors.ndim != 2:
        raise ValueError(f"Embeddings must be 2D, got {vectors.ndim}D")
    if vectors.shape[0] != n_works:
        raise ValueError(
            f"Embedding row mismatch: {vectors.shape[0]} vectors vs {n_works} works"
        )
