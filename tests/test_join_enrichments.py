"""Tests for join_enrichments.py — assembles enriched_works.csv from caches.

Ticket #428: each enrichment writes to its own cache; this script joins them.
"""

import os
import json

import pandas as pd
import pytest

# Import after path setup
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


@pytest.fixture
def enrichment_dir(tmp_path):
    """Create a minimal enrichment environment with base CSV and caches."""
    catalogs = tmp_path / "catalogs"
    cache_dir = catalogs / "enrich_cache"
    cache_dir.mkdir(parents=True)

    # Base unified_works.csv — 3 rows, 21 columns
    base = pd.DataFrame({
        "source": ["openalex", "istex", "bibcnrs"],
        "source_id": ["W001", "IST002", "BIB003"],
        "doi": ["10.1234/a", "", "10.1234/c"],
        "title": ["Title A", "Title B", "Title C"],
        "first_author": ["Auth A", "Auth B", "Auth C"],
        "all_authors": ["Auth A", "Auth B", "Auth C"],
        "year": [2020, 2021, 2022],
        "journal": ["J1", "J2", "J3"],
        "abstract": ["Abstract A text here.", "", ""],
        "language": ["en", "", ""],
        "keywords": ["kw1", "kw2", "kw3"],
        "categories": ["cat1", "cat2", "cat3"],
        "cited_by_count": [10, 5, 3],
        "affiliations": ["Aff1", "Aff2", "Aff3"],
        "from_openalex": [1, 0, 0],
        "from_istex": [0, 1, 0],
        "from_bibcnrs": [0, 0, 1],
        "from_scispace": [0, 0, 0],
        "from_grey": [0, 0, 0],
        "from_teaching": [0, 0, 0],
        "source_count": [1, 1, 1],
    })
    base.to_csv(catalogs / "unified_works.csv", index=False)

    # DOI cache — resolves IST002
    doi_cache = pd.DataFrame({
        "source_id": ["IST002"],
        "doi": ["10.1234/b"],
    })
    doi_cache.to_csv(cache_dir / "doi_resolved.csv", index=False)

    # Abstract caches
    oa_abs = pd.DataFrame({
        "key": ["W001"],
        "abstract": ["OpenAlex abstract for W001."],
    })
    oa_abs.to_csv(cache_dir / "openalex_abstracts.csv", index=False)

    s2_abs = pd.DataFrame({
        "key": ["10.1234/b"],
        "abstract": ["S2 abstract for IST002 via DOI."],
    })
    s2_abs.to_csv(cache_dir / "s2_abstracts.csv", index=False)

    # Language cache
    lang = pd.DataFrame({
        "key": ["10.1234/b", "10.1234/c"],
        "language": ["fr", "de"],
    })
    lang.to_csv(cache_dir / "language_resolved.csv", index=False)

    # Abstract summaries cache (JSONL) — empty for this test
    (cache_dir / "abstract_summaries_cache.jsonl").write_text("")

    return catalogs


EXPECTED_COLUMNS = [
    "source", "source_id", "doi", "title", "first_author", "all_authors",
    "year", "journal", "abstract", "language", "keywords", "categories",
    "cited_by_count", "affiliations",
    "from_openalex", "from_istex", "from_bibcnrs", "from_scispace",
    "from_grey", "from_teaching", "source_count",
    "abstract_status",
]


def test_join_produces_all_columns(enrichment_dir):
    """join_enrichments.py output has all expected columns."""
    from enrich_join import join_enrichments

    output_path = enrichment_dir / "enriched_works.csv"
    join_enrichments(
        unified_path=str(enrichment_dir / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(enrichment_dir / "enrich_cache"),
    )

    result = pd.read_csv(output_path)
    for col in EXPECTED_COLUMNS:
        assert col in result.columns, f"Missing column: {col}"


def test_join_applies_doi_cache(enrichment_dir):
    """DOI cache entries fill missing DOIs."""
    from enrich_join import join_enrichments

    output_path = enrichment_dir / "enriched_works.csv"
    join_enrichments(
        unified_path=str(enrichment_dir / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(enrichment_dir / "enrich_cache"),
    )

    result = pd.read_csv(output_path)
    ist_row = result[result["source_id"] == "IST002"].iloc[0]
    assert ist_row["doi"] == "10.1234/b", "DOI cache not applied"


def test_join_applies_abstract_caches(enrichment_dir):
    """Abstract caches fill missing abstracts."""
    from enrich_join import join_enrichments

    output_path = enrichment_dir / "enriched_works.csv"
    join_enrichments(
        unified_path=str(enrichment_dir / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(enrichment_dir / "enrich_cache"),
    )

    result = pd.read_csv(output_path)
    ist_row = result[result["source_id"] == "IST002"].iloc[0]
    assert ist_row["abstract"] == "S2 abstract for IST002 via DOI."


def test_join_applies_language_cache(enrichment_dir):
    """Language cache fills missing language tags."""
    from enrich_join import join_enrichments

    output_path = enrichment_dir / "enriched_works.csv"
    join_enrichments(
        unified_path=str(enrichment_dir / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(enrichment_dir / "enrich_cache"),
    )

    result = pd.read_csv(output_path)
    ist_row = result[result["source_id"] == "IST002"].iloc[0]
    assert ist_row["language"] == "fr"
    bib_row = result[result["source_id"] == "BIB003"].iloc[0]
    assert bib_row["language"] == "de"


def test_join_preserves_existing_values(enrichment_dir):
    """Existing non-null values are not overwritten by caches."""
    from enrich_join import join_enrichments

    output_path = enrichment_dir / "enriched_works.csv"
    join_enrichments(
        unified_path=str(enrichment_dir / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(enrichment_dir / "enrich_cache"),
    )

    result = pd.read_csv(output_path)
    w001 = result[result["source_id"] == "W001"].iloc[0]
    # Original abstract should be kept, not overwritten by OA cache
    assert w001["abstract"] == "Abstract A text here."
    assert w001["language"] == "en"
    assert w001["doi"] == "10.1234/a"


def test_crossfill_longest_abstract_wins(tmp_path):
    """Cross-source backfill picks the longest abstract for a given DOI."""
    from enrich_join import join_enrichments

    catalogs = tmp_path / "catalogs"
    cache_dir = catalogs / "enrich_cache"
    cache_dir.mkdir(parents=True)

    # Two records share the same DOI; one has a short abstract, one has a long one
    base = pd.DataFrame({
        "source": ["openalex", "istex"],
        "source_id": ["W100", "IST200"],
        "doi": ["10.1234/shared", "10.1234/shared"],
        "title": ["Title A", "Title B"],
        "first_author": ["Auth A", "Auth B"],
        "all_authors": ["Auth A", "Auth B"],
        "year": [2020, 2020],
        "journal": ["J1", "J2"],
        "abstract": ["Short.", "A much longer abstract with more detail and content."],
        "language": ["en", ""],
        "keywords": ["", ""],
        "categories": ["", ""],
        "cited_by_count": [10, 5],
        "affiliations": ["", ""],
        "from_openalex": [1, 0],
        "from_istex": [0, 1],
        "from_bibcnrs": [0, 0],
        "from_scispace": [0, 0],
        "from_grey": [0, 0],
        "from_teaching": [0, 0],
        "source_count": [1, 1],
    })
    base.to_csv(catalogs / "unified_works.csv", index=False)

    # Empty caches
    pd.DataFrame({"source_id": [], "doi": []}).to_csv(
        cache_dir / "doi_resolved.csv", index=False)
    pd.DataFrame({"key": [], "abstract": []}).to_csv(
        cache_dir / "openalex_abstracts.csv", index=False)
    pd.DataFrame({"key": [], "abstract": []}).to_csv(
        cache_dir / "s2_abstracts.csv", index=False)
    pd.DataFrame({"key": [], "language": []}).to_csv(
        cache_dir / "language_resolved.csv", index=False)
    (cache_dir / "abstract_summaries_cache.jsonl").write_text("")

    # Now blank the short abstract to trigger backfill
    base.at[0, "abstract"] = ""
    base.to_csv(catalogs / "unified_works.csv", index=False)

    output_path = catalogs / "enriched_works.csv"
    join_enrichments(
        unified_path=str(catalogs / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(cache_dir),
    )

    result = pd.read_csv(output_path)
    w100 = result[result["source_id"] == "W100"].iloc[0]
    assert "much longer" in w100["abstract"], (
        "Cross-source backfill should pick the longest abstract"
    )


def test_crossfill_ignores_nan_doi(tmp_path):
    """Cross-source backfill must not match records with NaN DOIs."""
    from enrich_join import join_enrichments

    catalogs = tmp_path / "catalogs"
    cache_dir = catalogs / "enrich_cache"
    cache_dir.mkdir(parents=True)

    # Two records both have NaN DOI — they should NOT cross-fill
    base = pd.DataFrame({
        "source": ["openalex", "istex"],
        "source_id": ["W100", "IST200"],
        "doi": [float("nan"), float("nan")],
        "title": ["Unrelated A", "Unrelated B"],
        "first_author": ["Auth A", "Auth B"],
        "all_authors": ["Auth A", "Auth B"],
        "year": [2020, 2021],
        "journal": ["J1", "J2"],
        "abstract": ["Has an abstract.", ""],
        "language": ["en", ""],
        "keywords": ["", ""],
        "categories": ["", ""],
        "cited_by_count": [10, 5],
        "affiliations": ["", ""],
        "from_openalex": [1, 0],
        "from_istex": [0, 1],
        "from_bibcnrs": [0, 0],
        "from_scispace": [0, 0],
        "from_grey": [0, 0],
        "from_teaching": [0, 0],
        "source_count": [1, 1],
    })
    base.to_csv(catalogs / "unified_works.csv", index=False)

    # Empty caches
    pd.DataFrame({"source_id": [], "doi": []}).to_csv(
        cache_dir / "doi_resolved.csv", index=False)
    pd.DataFrame({"key": [], "abstract": []}).to_csv(
        cache_dir / "openalex_abstracts.csv", index=False)
    pd.DataFrame({"key": [], "abstract": []}).to_csv(
        cache_dir / "s2_abstracts.csv", index=False)
    pd.DataFrame({"key": [], "language": []}).to_csv(
        cache_dir / "language_resolved.csv", index=False)
    (cache_dir / "abstract_summaries_cache.jsonl").write_text("")

    output_path = catalogs / "enriched_works.csv"
    join_enrichments(
        unified_path=str(catalogs / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(cache_dir),
    )

    result = pd.read_csv(output_path)
    ist = result[result["source_id"] == "IST200"].iloc[0]
    assert pd.isna(ist["abstract"]) or ist["abstract"] == "", (
        "NaN DOI records must not cross-fill abstracts from unrelated records"
    )


def test_join_missing_cache_files(tmp_path):
    """Join works gracefully when some cache files don't exist."""
    from enrich_join import join_enrichments

    catalogs = tmp_path / "catalogs"
    cache_dir = catalogs / "enrich_cache"
    cache_dir.mkdir(parents=True)

    base = pd.DataFrame({
        "source": ["openalex"],
        "source_id": ["W001"],
        "doi": ["10.1234/a"],
        "title": ["Title A"],
        "first_author": ["Auth A"],
        "all_authors": ["Auth A"],
        "year": [2020],
        "journal": ["J1"],
        "abstract": ["Abstract text."],
        "language": ["en"],
        "keywords": ["kw1"],
        "categories": ["cat1"],
        "cited_by_count": [10],
        "affiliations": ["Aff1"],
        "from_openalex": [1],
        "from_istex": [0],
        "from_bibcnrs": [0],
        "from_scispace": [0],
        "from_grey": [0],
        "from_teaching": [0],
        "source_count": [1],
    })
    base.to_csv(catalogs / "unified_works.csv", index=False)

    # No cache files at all — should not crash
    output_path = catalogs / "enriched_works.csv"
    join_enrichments(
        unified_path=str(catalogs / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(cache_dir),
    )

    result = pd.read_csv(output_path)
    assert len(result) == 1
    assert result.iloc[0]["abstract"] == "Abstract text."


def test_join_row_count_unchanged(enrichment_dir):
    """Join does not add or remove rows."""
    from enrich_join import join_enrichments

    output_path = enrichment_dir / "enriched_works.csv"
    join_enrichments(
        unified_path=str(enrichment_dir / "unified_works.csv"),
        output_path=str(output_path),
        cache_dir=str(enrichment_dir / "enrich_cache"),
    )

    base = pd.read_csv(enrichment_dir / "unified_works.csv")
    result = pd.read_csv(output_path)
    assert len(result) == len(base)
