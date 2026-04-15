"""Tests for architecture.md — pipeline phase rules and separation of concerns.

Enforces mechanically verifiable architecture rules from .claude/rules/architecture.md.
Each test prevents regressions; known pre-existing violations are allowlisted with
staleness guards that fail when a script is fixed (prompting allowlist cleanup).

Extracted from test_script_hygiene.py to keep both files under the 800-line wall.

Rules tested:
- Phase separation: Phase 2 scripts not in DVC, Feather handoff
- Rule 4: Compute/Plot/Include separation (analyze_* no figures, single output type)
- Rule 5: save_figure() mandatory in plot scripts
- Rule 7: Random seeds from config/analysis.yaml
- Rule 9: Corpus access through pipeline_loaders only
"""

import os
import re
from pathlib import Path

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO, "scripts")
MAKEFILE = os.path.join(REPO, "Makefile")
# Archived scripts are preserved for reference but not subject to checks.
ARCHIVE_DIR = os.path.join(SCRIPTS_DIR, "archive")

# ---------------------------------------------------------------------------
# Helpers (shared with test_script_hygiene.py — duplicated to avoid coupling)
# ---------------------------------------------------------------------------


def _all_scripts():
    """Return sorted list of .py files in scripts/ (excluding archive/)."""
    result = []
    for dirpath, dirnames, filenames in os.walk(SCRIPTS_DIR):
        rel_dir = os.path.relpath(dirpath, SCRIPTS_DIR)
        if rel_dir == "archive" or rel_dir.startswith("archive" + os.sep):
            dirnames.clear()
            continue
        for f in filenames:
            if f.endswith(".py") and not f.startswith("__"):
                rel = os.path.relpath(os.path.join(dirpath, f), SCRIPTS_DIR)
                result.append(rel)
    return sorted(result)


def _read_script(name):
    """Read a script by its path relative to SCRIPTS_DIR."""
    path = os.path.join(SCRIPTS_DIR, name)
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Phase separation: Phase 2 not in DVC
# ---------------------------------------------------------------------------


class TestNoPhaseTwoInDvc:
    """Phase 2 scripts must not be DVC stages (#527).

    Phase 2 (analyze_*, compute_*, plot_*, export_*) is fast and deterministic —
    outputs are Makefile targets, not DVC-tracked artifacts. Only Phase 1
    (catalog_*, enrich_*, corpus_*) belongs in dvc.yaml.
    """

    # summarize_abstracts is Phase 1 enrichment (writes to enrich_cache/), not Phase 2
    PHASE2_PREFIXES = ("analyze_", "compute_", "plot_", "export_")

    def test_no_phase2_stages_in_dvc(self):
        import yaml

        dvc_path = os.path.join(REPO, "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)
        phase2_stages = [
            s for s in dvc.get("stages", {}) if s.startswith(self.PHASE2_PREFIXES)
        ]
        assert phase2_stages == [], (
            f"Phase 2 stages found in dvc.yaml (should be Makefile targets): "
            f"{phase2_stages}"
        )


# ---------------------------------------------------------------------------
# Phase separation: Feather handoff
# ---------------------------------------------------------------------------


class TestFeatherHandoff:
    """Phase 2 loaders must read Feather, not CSV (#528).

    The Phase 1→2 handoff converts CSV to Feather for fast reads.
    load_analysis_corpus and load_refined_citations must use read_feather.
    """

    def test_load_analysis_corpus_reads_feather(self):
        source_path = os.path.join(SCRIPTS_DIR, "pipeline_loaders.py")
        with open(source_path) as f:
            source = f.read()
        assert "read_feather" in source, (
            "pipeline_loaders.py must use pd.read_feather for Phase 2 reads"
        )

    def test_feather_handoff_targets_in_makefile(self):
        with open(MAKEFILE) as f:
            content = f.read()
        assert ".feather" in content, (
            "Makefile must have handoff targets producing .feather files"
        )


# ---------------------------------------------------------------------------
# Rule 4: analyze_* scripts must not produce figures
# ---------------------------------------------------------------------------


class TestAnalyzeNoFigures:
    """analyze_* scripts compute data, not figures.

    The naming convention: analyze_* → data artifacts, plot_* → figures.
    Calling save_figure() or .savefig() in an analyze_ script is a
    separation-of-concerns violation.

    Tickets: #550 (bimodality), #551 (embeddings), #552 (cocitation).
    """

    # Scripts already split — should stay clean.
    CLEAN_ANALYZE = [
        "analyze_embeddings.py",
    ]

    @pytest.mark.parametrize("script", CLEAN_ANALYZE)
    def test_analyze_scripts_no_save_figure(self, script):
        path = os.path.join(SCRIPTS_DIR, script)
        src = Path(path).read_text()
        assert "save_figure" not in src and ".savefig(" not in src, (
            f"{script} calls save_figure/savefig — analyze_ scripts "
            f"should produce data only, not figures"
        )


# ---------------------------------------------------------------------------
# Rule 4: each plot script produces exactly one output type
# ---------------------------------------------------------------------------


class TestSingleOutputType:
    """Each plot_* script should produce exactly one visual output type.

    A script that writes both a static figure (save_figure/savefig) and an
    interactive HTML file bundles two renderers in one module. Split them
    following the genealogy pattern: plot_X.py (PNG) + plot_X_html.py (HTML).
    """

    def test_plot_scripts_single_output_type(self):
        """No plot_* script produces both PNG and HTML."""
        violations = []
        for name in _all_scripts():
            if not name.startswith("plot_"):
                continue
            path = os.path.join(SCRIPTS_DIR, name)
            src = Path(path).read_text()
            has_static = "save_figure" in src or "savefig" in src
            has_html = ".html" in src and (
                # Detect actual HTML file writing, not just docstring mentions
                bool(re.search(r"""open\(.*\.html""", src))
                or bool(re.search(r"""\.html['"]""", src))
            )
            if has_static and has_html:
                violations.append(name)
        assert not violations, (
            "Plot scripts producing both PNG and HTML (split into separate scripts): "
            + ", ".join(violations)
        )


# ---------------------------------------------------------------------------
# Rule 5: save_figure() mandatory in plot scripts
# ---------------------------------------------------------------------------


class TestSaveFigureMandatory:
    """Plot scripts must use save_figure() from pipeline_io.py, not .savefig().

    save_figure() strips metadata for byte-reproducible PNGs. Calling
    fig.savefig() directly bypasses this and breaks archive checksums.

    Architecture rule 5: "All plot scripts use save_figure(fig, stem, dpi=N)
    from pipeline_io.py — never call fig.savefig() directly."
    """

    # Pre-existing violations. Remove entries as they are migrated.
    KNOWN_VIOLATIONS = {
        "plot_fig_clustering_comparison.py",
        "plot_fig_clustering_spaces.py",
        "plot_fig_dag.py",
    }

    def test_plot_scripts_use_save_figure(self):
        """No plot_* script may call .savefig() directly (use save_figure())."""
        violations = []
        for name in _all_scripts():
            if not name.startswith("plot_"):
                continue
            if name in self.KNOWN_VIOLATIONS:
                continue
            src = _read_script(name)
            if ".savefig(" in src:
                violations.append(name)
        assert not violations, (
            f"plot_* scripts calling .savefig() directly "
            f"(must use save_figure() from pipeline_io.py): {violations}"
        )

    def test_known_violations_not_stale(self):
        """Every script in KNOWN_VIOLATIONS must still exist and still violate."""
        all_names = set(_all_scripts())
        for name in self.KNOWN_VIOLATIONS:
            assert name in all_names, (
                f"KNOWN_VIOLATIONS entry '{name}' no longer exists — remove it"
            )
            src = _read_script(name)
            assert ".savefig(" in src, (
                f"'{name}' no longer calls .savefig() — remove it from KNOWN_VIOLATIONS"
            )


# ---------------------------------------------------------------------------
# Rule 7: Random seeds from config
# ---------------------------------------------------------------------------


class TestNoHardcodedSeeds:
    """Phase 2 scripts must read random seeds from config/analysis.yaml.

    Architecture rule 7: "Every stochastic operation reads its seed from
    config/analysis.yaml. No hardcoded seed=42 or RandomState(42)."

    Detection: regex scan for literal integer arguments to known seed
    parameters (random_state=N, seed=N) and RandomState(N) calls.
    """

    _PHASE2_PREFIXES = (
        "analyze_",
        "compute_",
        "plot_",
        "export_",
        "summarize_",
        "build_het_core",
    )

    # Pre-existing violations. Remove entries as they are migrated to config.
    KNOWN_VIOLATIONS = {
        "analyze_bimodality.py",
        "analyze_cocitation.py",
        "analyze_communities_clusters.py",
        "analyze_embeddings.py",
        "analyze_multilingual.py",
        "analyze_unfccc_topics.py",
        "compute_breakpoints.py",
        "compute_clusters.py",
        "compute_lexical.py",
        "compute_temporal_communities.py",
        "plot_alluvial_html.py",
        "plot_bimodality.py",
        "plot_cocitation.py",
        "plot_fig45_pca_scatter.py",
        "plot_fig_traditions.py",
        "plot_figS_kde.py",
        "plot_heatmap_communities_clusters.py",
        "plot_ncc_bimodality.py",
    }

    # Patterns that indicate a hardcoded seed (literal int in seed position).
    _SEED_PATTERNS = [
        r"random_state\s*=\s*\d+",
        r"(?<!\w)seed\s*=\s*\d+",
        r"RandomState\(\s*\d+\s*\)",
        r"np\.random\.seed\(\s*\d+\s*\)",
        r"random\.seed\(\s*\d+\s*\)",
        r"RANDOM_STATE\s*=\s*\d+",
    ]

    def _has_hardcoded_seed(self, source):
        for pattern in self._SEED_PATTERNS:
            if re.search(pattern, source):
                return True
        return False

    def test_no_new_hardcoded_seeds(self):
        """No Phase 2 script (outside known violations) may hardcode seeds."""
        violations = []
        for name in _all_scripts():
            if not name.startswith(self._PHASE2_PREFIXES):
                continue
            if name in self.KNOWN_VIOLATIONS:
                continue
            src = _read_script(name)
            if self._has_hardcoded_seed(src):
                violations.append(name)
        assert not violations, (
            f"Phase 2 scripts with hardcoded seeds "
            f"(must read from config/analysis.yaml): {violations}"
        )

    def test_known_violations_not_stale(self):
        """Every script in KNOWN_VIOLATIONS must still exist and still violate."""
        all_names = set(_all_scripts())
        for name in sorted(self.KNOWN_VIOLATIONS):
            assert name in all_names, (
                f"KNOWN_VIOLATIONS entry '{name}' no longer exists — remove it"
            )
            src = _read_script(name)
            assert self._has_hardcoded_seed(src), (
                f"'{name}' no longer has hardcoded seeds — "
                f"remove it from KNOWN_VIOLATIONS"
            )


# ---------------------------------------------------------------------------
# Rule 9: Corpus access through loaders only
# ---------------------------------------------------------------------------


class TestCorpusThroughLoaders:
    """Phase 2 scripts must use pipeline_loaders, not direct pd.read_csv().

    Architecture rule 9: "Never call pd.read_csv() / np.load() /
    pd.read_feather() on contract files directly. Use pipeline_loaders."

    Detection: scan for read_csv/np.load/read_feather near contract
    filenames (refined_works, refined_embeddings, refined_citations).
    """

    _PHASE2_PREFIXES = (
        "analyze_",
        "compute_",
        "plot_",
        "export_",
        "summarize_",
        "build_het_core",
    )

    # The loader module itself is obviously exempt.
    _EXEMPT = {"pipeline_loaders.py"}

    # Pre-existing violations. Remove entries as they are migrated.
    KNOWN_VIOLATIONS = {
        "analyze_100bn.py",
        "analyze_bimodality.py",
        "analyze_cocitation.py",
        "analyze_communities_clusters.py",
        "analyze_genealogy.py",
        "compute_temporal_communities.py",
        "export_tab_venues.py",
        "plot_alluvial_html.py",
        "plot_fig_seed_axis.py",
        "plot_interactive_corpus.py",
    }

    _CONTRACT_FILES = re.compile(r"refined_works|refined_citations|refined_embeddings")
    _DIRECT_READ = re.compile(r"read_csv|read_feather|np\.load")

    def _has_direct_contract_read(self, source):
        """Return True if source reads a contract file without loaders."""
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "pipeline_loaders" in line:
                continue
            if self._DIRECT_READ.search(line) and self._CONTRACT_FILES.search(line):
                return True
        return False

    def test_no_new_direct_contract_reads(self):
        """No Phase 2 script (outside known violations) may read contract
        files directly — use pipeline_loaders instead."""
        violations = []
        for name in _all_scripts():
            if not name.startswith(self._PHASE2_PREFIXES):
                continue
            if name in self._EXEMPT or name in self.KNOWN_VIOLATIONS:
                continue
            src = _read_script(name)
            if self._has_direct_contract_read(src):
                violations.append(name)
        assert not violations, (
            f"Phase 2 scripts reading contract files directly "
            f"(must use pipeline_loaders): {violations}"
        )

    def test_known_violations_not_stale(self):
        """Every script in KNOWN_VIOLATIONS must still exist and still violate."""
        all_names = set(_all_scripts())
        for name in sorted(self.KNOWN_VIOLATIONS):
            assert name in all_names, (
                f"KNOWN_VIOLATIONS entry '{name}' no longer exists — remove it"
            )
            src = _read_script(name)
            assert self._has_direct_contract_read(src), (
                f"'{name}' no longer reads contract files directly — "
                f"remove it from KNOWN_VIOLATIONS"
            )
