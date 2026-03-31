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
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
GOLDEN_PATH = os.path.join(ROOT, "tests", "fixtures", "smoke", "golden_hashes.json")

sys.path.insert(0, SCRIPTS_DIR)
from compute_regression_hashes import REGISTRY, _hash_output, _smoke_env  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.pop(0)

ROOT_PATH = Path(ROOT).resolve()


def _load_golden() -> dict:
    with open(GOLDEN_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Shared fixture: run scripts in dependency order, backup/restore outputs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def regression_outputs(tmp_path_factory):
    """Run scripts in parallel waves, return {name: {file: hash}}.

    Uses module scope — all scripts run once per test session.
    Wave 1 (5 independent scripts) and wave 2 (4 dependent scripts)
    each run in parallel via ThreadPoolExecutor.
    """
    import shutil
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from compute_regression_hashes import _resolve_waves

    tmp = tmp_path_factory.mktemp("regression_backup")
    env = _smoke_env()

    # Backup existing outputs
    backups: dict[str, Path | None] = {}
    for entry in REGISTRY:
        for rel_path in entry["outputs"]:
            abs_path = ROOT_PATH / rel_path
            if abs_path.exists():
                dst = tmp / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(abs_path, dst)
                backups[rel_path] = dst
            else:
                backups[rel_path] = None

    # Ensure output dirs exist
    (ROOT_PATH / "content" / "tables").mkdir(parents=True, exist_ok=True)
    (ROOT_PATH / "content" / "figures").mkdir(parents=True, exist_ok=True)

    # Run scripts in parallel waves
    results: dict[str, dict[str, str]] = {}
    errors: dict[str, str] = {}

    def _run_entry(entry):
        name = entry["name"]
        script = os.path.join(SCRIPTS_DIR, entry["script"])
        proc = subprocess.run(
            [sys.executable, script, *entry["args"]],
            capture_output=True, text=True, env=env, timeout=120,
        )
        if proc.returncode != 0:
            return name, None, proc.stderr[:500]
        hashes = {}
        for rel_path in entry["outputs"]:
            abs_path = ROOT_PATH / rel_path
            if abs_path.exists():
                hashes[rel_path] = _hash_output(abs_path)
        return name, hashes, None

    for wave in _resolve_waves():
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            futures = [pool.submit(_run_entry, e) for e in wave]
            for future in as_completed(futures):
                name, hashes, err = future.result()
                if err:
                    errors[name] = err
                else:
                    results[name] = hashes

    # Restore backups
    for rel_path, backup_path in backups.items():
        abs_path = ROOT_PATH / rel_path
        if backup_path is not None:
            shutil.copy2(backup_path, abs_path)
        elif abs_path.exists():
            abs_path.unlink()

    return results, errors


# ---------------------------------------------------------------------------
# One test per script — pinpoints exactly which output changed
# ---------------------------------------------------------------------------

def _make_test(entry):
    """Factory: create a test function for one registry entry."""
    name = entry["name"]

    @pytest.mark.integration
    def test_func(regression_outputs):
        results, errors = regression_outputs
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


class TestRegressionIsolation:
    """Regression outputs must not touch content/ directories."""

    @pytest.mark.integration
    def test_regression_outputs_do_not_touch_content_dir(self, regression_outputs):
        """After regression_outputs runs, no file under content/figures/ or
        content/tables/ should have been created or modified.

        The fixture should redirect all outputs to a tmp directory, so the
        real content/ tree stays untouched.
        """
        import time

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
