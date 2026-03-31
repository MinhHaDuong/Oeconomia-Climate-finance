"""Regression tests: Phase 2 script outputs vs golden hash baseline.

Each registered script runs on the 100-row smoke fixture, its outputs
are hashed (with float-rounding tolerance for CSV/JSON), and compared
against golden_hashes.json.

Run as part of `make check` (via pytest). One test per script, so
failures pinpoint exactly which script's output changed.

When a change is intentional:
    uv run python scripts/compute_regression_hashes.py --update-golden
    git add tests/fixtures/smoke/golden_hashes.json
    # commit with explanation of why outputs changed
"""

import json
import os
import time

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
GOLDEN_PATH = os.path.join(ROOT, "tests", "fixtures", "smoke", "golden_hashes.json")

import sys  # noqa: E402
sys.path.insert(0, SCRIPTS_DIR)
from compute_regression_hashes import (  # noqa: E402
    REGISTRY, ROOT as HARNESS_ROOT, _hash_output, _redirect_args, _smoke_env,
)
from pathlib import Path  # noqa: E402

sys.path.pop(0)

ROOT_PATH = Path(ROOT).resolve()


def _load_golden() -> dict:
    with open(GOLDEN_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Shared fixture: run scripts with outputs redirected to tmp
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def regression_outputs(tmp_path_factory):
    """Run scripts in parallel waves, return (results, errors, start_time).

    Uses module scope — all scripts run once per test session.
    Outputs are redirected to a temporary directory via run_and_hash(output_root=...),
    so the real content/ tree is never touched.
    """
    from compute_regression_hashes import run_and_hash

    start_time = time.time()
    tmp = tmp_path_factory.mktemp("regression_outputs")

    try:
        results = run_and_hash(output_root=tmp)
        return results, {}, start_time
    except Exception as exc:
        return {}, {"__harness__": str(exc)[:500]}, start_time


# ---------------------------------------------------------------------------
# One test per script — pinpoints exactly which output changed
# ---------------------------------------------------------------------------

def _make_test(entry):
    """Factory: create a test function for one registry entry."""
    name = entry["name"]

    @pytest.mark.integration
    def test_func(regression_outputs):
        results, errors, _start_time = regression_outputs
        if name in errors:
            pytest.fail(f"{name} failed to run:\n{errors[name]}")

        golden = _load_golden()
        assert name in golden, (
            f"{name} not in golden_hashes.json. Run: "
            "uv run python scripts/compute_regression_hashes.py --update-golden"
        )
        assert name in results, f"{name} produced no outputs"

        for rel_path, expected_hash in golden[name].items():
            actual_hash = results[name].get(rel_path)
            assert actual_hash is not None, f"{name}: missing output {rel_path}"
            assert actual_hash == expected_hash, (
                f"{name}: {os.path.basename(rel_path)} changed\n"
                f"  golden:  {expected_hash[:16]}...\n"
                f"  current: {actual_hash[:16]}...\n"
                "If intentional: uv run python scripts/compute_regression_hashes.py --update-golden"
            )

    test_func.__name__ = f"test_regression_{name}"
    test_func.__qualname__ = f"test_regression_{name}"
    return test_func


# Generate one test per registry entry
for _entry in REGISTRY:
    globals()[f"test_regression_{_entry['name']}"] = _make_test(_entry)


# ---------------------------------------------------------------------------
# Infrastructure tests (fast, no script execution)
# ---------------------------------------------------------------------------

class TestRegressionInfra:
    """Regression infrastructure exists and is wired up."""

    def test_golden_hashes_exist(self):
        assert os.path.exists(GOLDEN_PATH), (
            "Golden hashes not found. Generate with: "
            "uv run python scripts/compute_regression_hashes.py --update-golden"
        )

    def test_golden_hashes_valid_json(self):
        data = _load_golden()
        assert len(data) > 0, "Golden hashes file is empty"

    def test_golden_covers_registry(self):
        golden = _load_golden()
        registry_names = {e["name"] for e in REGISTRY}
        golden_names = set(golden.keys())
        missing = registry_names - golden_names
        assert not missing, (
            f"Golden hashes missing for: {missing}. "
            "Run: uv run python scripts/compute_regression_hashes.py --update-golden"
        )

    def test_makefile_has_regression_target(self):
        import re
        with open(os.path.join(ROOT, "Makefile")) as f:
            content = f.read()
        assert re.search(r"^regression\s*:", content, re.MULTILINE), (
            "Makefile missing 'regression' target"
        )

    def test_no_stage_intermediates_function(self):
        """_stage_intermediates was removed: Wave 2 scripts now accept --input,
        so the harness no longer needs to copy intermediates into content/."""
        import scripts.compute_regression_hashes as mod
        assert not hasattr(mod, "_stage_intermediates"), (
            "compute_regression_hashes still has _stage_intermediates; "
            "Wave 2 scripts should accept --input instead"
        )
        assert not hasattr(mod, "_cleanup_intermediates"), (
            "compute_regression_hashes still has _cleanup_intermediates; "
            "remove it along with _stage_intermediates"
        )

    def test_wave2_registry_entries_have_input_args(self):
        """Wave 2 scripts (with deps) must pass --input in their REGISTRY args,
        so the harness can point them at the tmp directory directly."""
        for entry in REGISTRY:
            if entry["deps"]:
                assert "--input" in entry["args"], (
                    f"REGISTRY[{entry['name']}] has deps {entry['deps']} "
                    "but no --input in args — Wave 2 scripts need --input "
                    "to avoid intermediate staging"
                )


class TestRedirectArgs:
    """Unit tests for _redirect_args path rewriting."""

    def test_relative_content_path_redirected(self, tmp_path):
        args = ["--output", "content/figures/fig_bars.png"]
        result = _redirect_args(args, tmp_path)
        assert result[0] == "--output"
        assert result[1] == str(tmp_path / "content" / "figures" / "fig_bars.png")

    def test_absolute_path_under_root_redirected(self, tmp_path):
        abs_path = str(HARNESS_ROOT / "content" / "tables" / "tab.csv")
        args = ["--output", abs_path]
        result = _redirect_args(args, tmp_path)
        assert result[1] == str(tmp_path / "content" / "tables" / "tab.csv")

    def test_non_content_arg_unchanged(self, tmp_path):
        args = ["--robustness", "--v1-only"]
        result = _redirect_args(args, tmp_path)
        assert result == ["--robustness", "--v1-only"]

    def test_tests_path_redirected(self, tmp_path):
        args = ["--output", "tests/fixtures/smoke/catalogs/het_mostcited_50.csv"]
        result = _redirect_args(args, tmp_path)
        assert "tests/fixtures/smoke/catalogs" in result[1]
        assert str(tmp_path) in result[1]

    def test_all_registry_args_use_relative_paths(self):
        """All REGISTRY entries should use relative (not absolute) paths in args."""
        for entry in REGISTRY:
            for arg in entry["args"]:
                if arg.startswith("--"):
                    continue
                assert not Path(arg).is_absolute(), (
                    f"REGISTRY[{entry['name']}] has absolute path in args: {arg}"
                )


class TestRegressionIsolation:
    """Regression outputs must not touch content/ directories."""

    @pytest.mark.integration
    def test_regression_outputs_do_not_touch_content_dir(self, regression_outputs):
        """After regression_outputs runs, no file under content/figures/ or
        content/tables/ should have been created or modified.

        The fixture should redirect all outputs to a tmp directory, so the
        real content/ tree stays untouched.
        """
        # regression_outputs already ran (module-scoped fixture).
        # Check that it returned a start_time we can compare against.
        results, errors, start_time = regression_outputs

        content_dirs = [
            ROOT_PATH / "content" / "figures",
            ROOT_PATH / "content" / "tables",
        ]
        touched = []
        for d in content_dirs:
            if not d.exists():
                continue
            for f in d.iterdir():
                if f.is_file() and f.stat().st_mtime > start_time:
                    touched.append(str(f.relative_to(ROOT_PATH)))

        assert not touched, (
            f"Regression fixture modified files in content/:\n"
            + "\n".join(f"  {p}" for p in touched)
        )
