"""Tests for zoo.mk structure — schematic + result panel recipes."""

import re
from pathlib import Path

ZOO_MK = Path(__file__).resolve().parent.parent / "zoo.mk"


def read_zoo_mk() -> str:
    return ZOO_MK.read_text()


class TestZooMkStructure:
    def test_zoo_figures_is_phony(self):
        mk = read_zoo_mk()
        assert re.search(r"^\.PHONY:.*zoo-figures", mk, re.MULTILINE), (
            "zoo-figures must be declared .PHONY"
        )

    def test_zoo_figures_target_exists(self):
        mk = read_zoo_mk()
        assert re.search(r"^zoo-figures\s*:", mk, re.MULTILINE), (
            "zoo-figures target missing from zoo.mk"
        )

    def test_schematic_pattern_recipe_exists(self):
        mk = read_zoo_mk()
        assert re.search(r"schematic_%\.png\s*:.*plot_schematic_%\.py", mk), (
            "Pattern rule for schematic_%.png missing from zoo.mk"
        )

    def test_result_panel_pattern_recipe_exists(self):
        mk = read_zoo_mk()
        assert re.search(r"fig_zoo_%\.png\s*:.*plot_zoo_results\.py", mk), (
            "Pattern rule for fig_zoo_%.png missing from zoo.mk"
        )

    def test_crossyear_tables_is_phony(self):
        mk = read_zoo_mk()
        assert re.search(r"^\.PHONY:.*crossyear-tables", mk, re.MULTILINE), (
            "crossyear-tables must be declared .PHONY"
        )

    def test_crossyear_methods_has_18_methods(self):
        mk = read_zoo_mk()
        m = re.search(
            r"^CROSSYEAR_METHODS\s*:=\s*(.*?)(?=\n\S|\n\n|\Z)",
            mk,
            re.MULTILINE | re.DOTALL,
        )
        assert m, "CROSSYEAR_METHODS not found in zoo.mk"
        methods = [t for t in m.group(1).split() if t != "\\"]
        assert len(methods) == 18, (
            f"Expected 18 CROSSYEAR_METHODS, got {len(methods)}: {methods}"
        )

    def test_cumulative_methods_included(self):
        """L3, G3, G4, G7 use cumulative/single windows — must still have recipes."""
        mk = read_zoo_mk()
        m = re.search(
            r"^CROSSYEAR_METHODS\s*:=\s*(.*?)(?=\n\S|\n\n|\Z)",
            mk,
            re.MULTILINE | re.DOTALL,
        )
        assert m, "CROSSYEAR_METHODS not found"
        methods = [t for t in m.group(1).split() if t != "\\"]
        for expected in (
            "L3",
            "G3_coupling_age",
            "G4_cross_tradition",
            "G7_disruption",
        ):
            assert expected in methods, f"{expected} missing from CROSSYEAR_METHODS"
