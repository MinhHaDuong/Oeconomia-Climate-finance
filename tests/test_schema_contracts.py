"""Tests for #513: Schema contracts at Phase 1→2 handoff boundaries.

Verifies that pandera schemas exist for the 3 contract files and that
the smoke fixture data passes validation.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Schema module exists
# ---------------------------------------------------------------------------

class TestSchemaModuleExists:
    def test_schemas_importable(self):
        from schemas import RefinedWorksSchema, RefinedCitationsSchema
        assert RefinedWorksSchema is not None
        assert RefinedCitationsSchema is not None

    def test_embeddings_schema_importable(self):
        from schemas import validate_refined_embeddings
        assert callable(validate_refined_embeddings)


# ---------------------------------------------------------------------------
# Smoke fixture validates against schemas
# ---------------------------------------------------------------------------

class TestSmokeFixtureMatchesSchema:
    """The 100-row smoke fixture passes schema validation."""

    def test_refined_works_schema(self):
        from schemas import RefinedWorksSchema
        df = pd.read_csv(
            os.path.join(FIXTURE_DIR, "refined_works.csv"),
            dtype=str, keep_default_na=False,
        )
        RefinedWorksSchema.validate(df)

    def test_refined_citations_schema(self):
        from schemas import RefinedCitationsSchema
        df = pd.read_csv(
            os.path.join(FIXTURE_DIR, "refined_citations.csv"),
            dtype=str, keep_default_na=False,
        )
        RefinedCitationsSchema.validate(df)

    def test_refined_embeddings_schema(self):
        from schemas import validate_refined_embeddings
        vectors = np.load(
            os.path.join(FIXTURE_DIR, "refined_embeddings.npz")
        )["vectors"]
        n_works = len(pd.read_csv(
            os.path.join(FIXTURE_DIR, "refined_works.csv")
        ))
        validate_refined_embeddings(vectors, n_works)


# ---------------------------------------------------------------------------
# Schema rejects bad data
# ---------------------------------------------------------------------------

class TestSchemaRejectsBadData:
    """Schemas catch common contract violations."""

    def test_missing_required_column(self):
        from schemas import RefinedWorksSchema
        import pandera as pa
        df = pd.DataFrame({"title": ["test"], "year": ["2020"]})
        with pytest.raises(pa.errors.SchemaError):
            RefinedWorksSchema.validate(df)

    def test_embeddings_row_mismatch(self):
        from schemas import validate_refined_embeddings
        vectors = np.zeros((5, 10))
        with pytest.raises(ValueError, match="mismatch"):
            validate_refined_embeddings(vectors, n_works=10)
