"""Pandera schemas for Phase 1→2 contract files.

Declares the expected shape of the 3 handoff artifacts:
- refined_works.csv — corpus metadata
- refined_citations.csv — citation edges
- refined_embeddings.npz — embedding vectors (validated via function)

Used by:
- corpus_align.py (writer side): validate before writing
- pipeline_loaders.py (reader side): validate on load
- tests/test_schema_contracts.py: verify fixture and real data
"""

import pandera as pa
from pandera import Column, DataFrameSchema

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
        raise ValueError(
            f"Embeddings must be 2D, got {vectors.ndim}D"
        )
    if vectors.shape[0] != n_works:
        raise ValueError(
            f"Embedding row mismatch: {vectors.shape[0]} vectors "
            f"vs {n_works} works"
        )
