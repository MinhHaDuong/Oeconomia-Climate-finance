"""Tests for zoo.mk structure — schematic + result panel recipes."""

import re
from pathlib import Path

import pytest

ZOO_MK = Path(__file__).resolve().parent.parent / "zoo.mk"

_CROSSYEAR_RE = re.compile(
    r"^CROSSYEAR_METHODS\s*:=\s*(.*?)(?=\n\S|\n\n|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _parse_crossyear_methods(mk: str) -> list[str]:
    m = _CROSSYEAR_RE.search(mk)
    assert m, "CROSSYEAR_METHODS not found in zoo.mk"
    return [t for t in m.group(1).split() if t != "\\"]


@pytest.fixture(scope="class")
def zoo_mk_text():
    return ZOO_MK.read_text()


class TestZooMkStructure:
    def test_zoo_figures_is_phony(self, zoo_mk_text):
        assert re.search(r"^\.PHONY:.*zoo-figures", zoo_mk_text, re.MULTILINE), (
            "zoo-figures must be declared .PHONY"
        )

    def test_zoo_figures_target_exists(self, zoo_mk_text):
        assert re.search(r"^zoo-figures\s*:", zoo_mk_text, re.MULTILINE), (
            "zoo-figures target missing from zoo.mk"
        )

    def test_schematic_pattern_recipe_exists(self, zoo_mk_text):
        assert re.search(r"schematic_%\.png\s*:.*plot_schematic_%\.py", zoo_mk_text), (
            "Pattern rule for schematic_%.png missing from zoo.mk"
        )

    def test_result_panel_pattern_recipe_exists(self, zoo_mk_text):
        assert re.search(r"fig_zoo_%\.png\s*:.*plot_zoo_results\.py", zoo_mk_text), (
            "Pattern rule for fig_zoo_%.png missing from zoo.mk"
        )

    def test_crossyear_tables_is_phony(self, zoo_mk_text):
        assert re.search(r"^\.PHONY:.*crossyear-tables", zoo_mk_text, re.MULTILINE), (
            "crossyear-tables must be declared .PHONY"
        )

    def test_crossyear_methods_has_18_methods(self, zoo_mk_text):
        methods = _parse_crossyear_methods(zoo_mk_text)
        assert len(methods) == 18, (
            f"Expected 18 CROSSYEAR_METHODS, got {len(methods)}: {methods}"
        )

    def test_cumulative_methods_included(self, zoo_mk_text):
        """L3, G3, G4, G7 use cumulative/single windows — must still have recipes."""
        methods = _parse_crossyear_methods(zoo_mk_text)
        for expected in (
            "L3",
            "G3_coupling_age",
            "G4_cross_tradition",
            "G7_disruption",
        ):
            assert expected in methods, f"{expected} missing from CROSSYEAR_METHODS"

    def test_zoo_only_pdf_target_in_zoo_mk(self, zoo_mk_text):
        """zoo-only.pdf recipe must live in zoo.mk, not only in Makefile."""
        assert re.search(
            r"^output/content/zoo-only\.pdf\s*:", zoo_mk_text, re.MULTILINE
        ), "zoo-only.pdf recipe must live in zoo.mk"
