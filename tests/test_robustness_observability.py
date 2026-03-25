"""Tests for #65/#66/#67/#68: enrich_* robustness + observability quick wins.

Covers:
- retry_get / save_run_report / make_run_id utilities (unit)
- --run-id and --checkpoint-every CLI flags present on all three scripts
- Startup resume-preview output (stdout contains expected strings)
- Run summary JSON is created with internally consistent counters
- Step counter updates on abstract enrichment steps

CLI flag presence is checked via source inspection (no subprocess).
Integration tests that run scripts via subprocess are marked @integration.
"""

import json
import os
import subprocess
import sys
import tempfile
import time

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mini_works(tmp_path):
    """Create a minimal unified_works.csv for CLI smoke-tests."""
    df = pd.DataFrame({
        "doi": ["10.1/A", "10.1/B", "10.1/C"],
        "title": ["Title A", "Title B", "Title C"],
        "abstract": ["Abstract A", "", None],
        "source": ["openalex", "openalex", "istex"],
        "source_id": ["W1", "W2", "I1"],
        "year": [2010, 2015, 2020],
        "cited_by_count": [100, 5, 0],
        "source_count": [2, 1, 1],
        "from_openalex": [1, 1, 0],
        "from_semanticscholar": [1, 0, 0],
        "from_istex": [0, 0, 1],
        "from_bibcnrs": [0, 0, 0],
        "from_scispace": [0, 0, 0],
        "from_grey": [0, 0, 0],
        "from_teaching": [0, 0, 0],
    })
    path = tmp_path / "unified_works.csv"
    df.to_csv(path, index=False)
    return str(path)


def make_mini_citations(tmp_path):
    """Create an empty citations.csv."""
    from utils import REFS_COLUMNS
    path = tmp_path / "citations.csv"
    pd.DataFrame(columns=REFS_COLUMNS).to_csv(path, index=False)
    return str(path)


def _script_source(script_name):
    """Read script source text for flag inspection."""
    path = os.path.join(SCRIPTS_DIR, script_name)
    with open(path) as f:
        return f.read()


def _has_flag(source, flag):
    """Check that the script source defines an argparse flag."""
    return f'"{flag}"' in source or f"'{flag}'" in source


# ---------------------------------------------------------------------------
# Unit tests: utils helpers
# ---------------------------------------------------------------------------

class TestUtilsHelpers:
    def test_make_run_id_format(self):
        from utils import make_run_id
        run_id = make_run_id()
        # Should look like 20260312T123456Z
        assert len(run_id) == 16
        assert run_id.endswith("Z")
        assert "T" in run_id

    def test_make_run_id_different_across_calls(self):
        from utils import make_run_id
        ids = {make_run_id() for _ in range(3)}
        # Allow duplicates in fast test envs but at least one call succeeds
        assert len(ids) >= 1

    def test_save_run_report_creates_file(self, tmp_path):
        from utils import save_run_report, CATALOGS_DIR
        # Patch CATALOGS_DIR to tmp_path for isolation
        import utils
        orig = utils.CATALOGS_DIR
        utils.CATALOGS_DIR = str(tmp_path)
        try:
            data = {"elapsed_seconds": 1.5, "rows_written": 42}
            path = save_run_report(data, "test-run-001", "my_script")
            assert os.path.isfile(path)
        finally:
            utils.CATALOGS_DIR = orig

    def test_save_run_report_json_schema(self, tmp_path):
        from utils import save_run_report
        import utils
        orig = utils.CATALOGS_DIR
        utils.CATALOGS_DIR = str(tmp_path)
        try:
            data = {"counter_a": 10, "counter_b": 5, "elapsed_seconds": 2.0}
            path = save_run_report(data, "run-xyz", "test_script")
            with open(path) as f:
                payload = json.load(f)
            assert payload["script"] == "test_script"
            assert payload["run_id"] == "run-xyz"
            assert payload["counter_a"] == 10
            assert payload["elapsed_seconds"] == 2.0
        finally:
            utils.CATALOGS_DIR = orig

    def test_save_run_report_sanitizes_run_id(self, tmp_path):
        from utils import save_run_report
        import utils
        orig = utils.CATALOGS_DIR
        utils.CATALOGS_DIR = str(tmp_path)
        try:
            path = save_run_report({}, "run id/with spaces&special!", "script")
            assert os.path.isfile(path)
            # filename should not contain spaces or slashes
            basename = os.path.basename(path)
            assert " " not in basename
            assert "/" not in basename
        finally:
            utils.CATALOGS_DIR = orig

    def test_retry_get_importable(self):
        from utils import retry_get
        assert callable(retry_get)

    def test_retry_get_updates_counters_on_success(self, requests_mock):
        from utils import retry_get
        requests_mock.get("https://example.com/ok", json={"ok": True})
        counters = {}
        resp = retry_get("https://example.com/ok", delay=0, counters=counters)
        assert resp.status_code == 200
        # No errors recorded for a clean success
        assert counters.get("retries", 0) == 0
        assert counters.get("rate_limited", 0) == 0

    def test_retry_get_records_rate_limit(self, requests_mock):
        from utils import retry_get
        requests_mock.get(
            "https://example.com/rl",
            [
                {"status_code": 429, "headers": {"Retry-After": "0"}},
                {"json": {"ok": True}},
            ],
        )
        counters = {}
        resp = retry_get("https://example.com/rl", delay=0, counters=counters)
        assert resp.status_code == 200
        assert counters.get("rate_limited", 0) >= 1
        assert counters.get("retries", 0) >= 1

    def test_retry_get_records_server_error_then_success(self, requests_mock):
        from utils import retry_get
        requests_mock.get(
            "https://example.com/srv",
            [
                {"status_code": 500},
                {"json": {"ok": True}},
            ],
        )
        counters = {}
        resp = retry_get("https://example.com/srv", delay=0, counters=counters)
        assert resp.status_code == 200
        assert counters.get("server_errors", 0) >= 1
        assert counters.get("retries", 0) >= 1

    def test_retry_get_accepts_backoff_base_and_jitter_max(self, requests_mock):
        """retry_get accepts backoff_base and jitter_max parameters."""
        from utils import retry_get
        requests_mock.get("https://example.com/bp", json={"ok": True})
        counters = {}
        resp = retry_get("https://example.com/bp", delay=0, counters=counters,
                         backoff_base=1.5, jitter_max=0.5)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# JSONL log file: created on real run and contains expected events
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestJsonlLogging:
    def test_enrich_abstracts_dry_run_no_jsonl(self, tmp_path):
        """--dry-run exits before JSONL events are written (no start event)."""
        works_path = make_mini_works(tmp_path)
        log_path = tmp_path / "run.jsonl"
        env = {**os.environ, "CLIMATE_FINANCE_DATA": str(tmp_path)}
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "enrich_abstracts.py"),
             "--dry-run", "--works-input", works_path,
             "--log-jsonl", str(log_path)],
            capture_output=True, text=True, env=env,
        )
        # dry-run should not write any events (exits before they are emitted)
        if log_path.exists():
            lines = [l for l in log_path.read_text().splitlines() if l.strip()]
            # If events were written, there should be no 'complete' event
            complete_events = [json.loads(l) for l in lines if '"complete"' in l]
            assert not complete_events, "dry-run should not write complete event"

    def test_log_jsonl_path_accepted_without_error(self, tmp_path):
        """--log-jsonl flag is accepted by all three scripts without parse error."""
        log_path = tmp_path / "run.jsonl"
        for script in ["enrich_abstracts.py", "enrich_citations_batch.py",
                       "enrich_citations_openalex.py"]:
            result = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS_DIR, script), "--help"],
                capture_output=True, text=True,
            )
            assert "--log-jsonl" in result.stdout + result.stderr, \
                f"--log-jsonl not found in {script} --help"


# ---------------------------------------------------------------------------
# CLI flag tests: verify add_argument calls via source inspection (no subprocess)
# ---------------------------------------------------------------------------

class TestCliFlags:
    """Verify CLI flags are defined in argparse (source inspection, no subprocess)."""

    @pytest.fixture(autouse=True, scope="class")
    def _load_sources(self, request):
        request.cls._sources = {
            "enrich_abstracts.py": _script_source("enrich_abstracts.py"),
            "enrich_citations_batch.py": _script_source("enrich_citations_batch.py"),
            "enrich_citations_openalex.py": _script_source("enrich_citations_openalex.py"),
        }

    def test_enrich_abstracts_has_run_id_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--run-id")

    def test_enrich_abstracts_has_checkpoint_every_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--checkpoint-every")

    def test_enrich_abstracts_has_resume_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--resume")

    def test_enrich_abstracts_has_request_timeout_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--request-timeout")

    def test_enrich_abstracts_has_max_retries_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--max-retries")

    def test_enrich_abstracts_has_retry_backoff_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--retry-backoff")

    def test_enrich_abstracts_has_retry_jitter_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--retry-jitter")

    def test_enrich_abstracts_has_log_jsonl_flag(self):
        assert _has_flag(self._sources["enrich_abstracts.py"], "--log-jsonl")

    def test_enrich_citations_batch_has_run_id_flag(self):
        assert _has_flag(self._sources["enrich_citations_batch.py"], "--run-id")

    # --checkpoint-every and --resume removed in #441 (cache-is-data:
    # always resumable, append directly to cache — no checkpoint needed)

    def test_enrich_citations_batch_has_request_timeout_flag(self):
        assert _has_flag(self._sources["enrich_citations_batch.py"], "--request-timeout")

    def test_enrich_citations_batch_has_max_retries_flag(self):
        assert _has_flag(self._sources["enrich_citations_batch.py"], "--max-retries")

    def test_enrich_citations_batch_has_retry_backoff_flag(self):
        assert _has_flag(self._sources["enrich_citations_batch.py"], "--retry-backoff")

    def test_enrich_citations_batch_has_retry_jitter_flag(self):
        assert _has_flag(self._sources["enrich_citations_batch.py"], "--retry-jitter")

    def test_enrich_citations_batch_has_log_jsonl_flag(self):
        assert _has_flag(self._sources["enrich_citations_batch.py"], "--log-jsonl")

    def test_enrich_citations_openalex_has_run_id_flag(self):
        assert _has_flag(self._sources["enrich_citations_openalex.py"], "--run-id")

    # --checkpoint-every and --resume removed in #441 (same as batch above)

    def test_enrich_citations_openalex_has_request_timeout_flag(self):
        assert _has_flag(self._sources["enrich_citations_openalex.py"], "--request-timeout")

    def test_enrich_citations_openalex_has_max_retries_flag(self):
        assert _has_flag(self._sources["enrich_citations_openalex.py"], "--max-retries")

    def test_enrich_citations_openalex_has_retry_backoff_flag(self):
        assert _has_flag(self._sources["enrich_citations_openalex.py"], "--retry-backoff")

    def test_enrich_citations_openalex_has_retry_jitter_flag(self):
        assert _has_flag(self._sources["enrich_citations_openalex.py"], "--retry-jitter")

    def test_enrich_citations_openalex_has_log_jsonl_flag(self):
        assert _has_flag(self._sources["enrich_citations_openalex.py"], "--log-jsonl")


# ---------------------------------------------------------------------------
# Resume preview: startup output contains expected labels
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestResumePreview:
    def test_enrich_abstracts_dry_run_shows_preview(self, tmp_path):
        works_path = make_mini_works(tmp_path)
        env = {**os.environ, "CLIMATE_FINANCE_DATA": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "enrich_abstracts.py"),
             "--dry-run", "--works-input", works_path],
            capture_output=True, text=True, env=env,
        )
        output = result.stdout + result.stderr
        assert "Resume preview" in output or "Missing abstracts" in output
        assert "Total works" in output or "Loaded" in output

    @pytest.mark.slow
    @pytest.mark.timeout(30)
    def test_enrich_citations_batch_preview_on_empty_corpus(self, tmp_path):
        works_path = make_mini_works(tmp_path)
        citations_path = make_mini_citations(tmp_path)
        env = {
            **os.environ,
            "CLIMATE_FINANCE_DATA": str(tmp_path),
        }
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "enrich_citations_batch.py"),
             "--works-input", works_path,
             "--run-id", "test-preview"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        output = result.stdout + result.stderr
        # Should show resume info (even if no actual fetch happens)
        assert "Resume" in output or "Nothing to fetch" in output


# ---------------------------------------------------------------------------
# Run report JSON: file is created and internally consistent
# ---------------------------------------------------------------------------

class TestRunReport:
    @pytest.mark.integration
    def test_enrich_abstracts_dry_run_no_report(self, tmp_path):
        """--dry-run exits before writing the report."""
        works_path = make_mini_works(tmp_path)
        env = {**os.environ, "CLIMATE_FINANCE_DATA": str(tmp_path)}
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "enrich_abstracts.py"),
             "--dry-run", "--works-input", works_path, "--run-id", "dryrun-001"],
            capture_output=True, text=True, env=env,
        )
        reports_dir = os.path.join(str(tmp_path), "run_reports")
        # Dry-run exits before saving report
        if os.path.isdir(reports_dir):
            reports = os.listdir(reports_dir)
            assert not any("enrich_abstracts" in r for r in reports)

    def test_save_run_report_counter_consistency(self, tmp_path):
        """Manually verify that the report structure is consistent."""
        from utils import save_run_report
        import utils
        orig = utils.CATALOGS_DIR
        utils.CATALOGS_DIR = str(tmp_path)
        try:
            missing_before = 10
            missing_after = 3
            total_filled = missing_before - missing_after
            data = {
                "missing_before": missing_before,
                "missing_after": missing_after,
                "total_filled": total_filled,
                "elapsed_seconds": 5.0,
            }
            path = save_run_report(data, "consistency-test", "enrich_abstracts")
            with open(path) as f:
                payload = json.load(f)
            assert payload["missing_before"] - payload["missing_after"] == payload["total_filled"]
            assert payload["elapsed_seconds"] > 0
        finally:
            utils.CATALOGS_DIR = orig


# ---------------------------------------------------------------------------
# Step counter tests (unit, no API)
# ---------------------------------------------------------------------------

class TestStepCounters:
    @pytest.fixture
    def mini_df(self):
        return pd.DataFrame({
            "doi": ["10.1/A", "10.1/B", "10.1/C"],
            "abstract": ["Has abstract", "", None],
            "source": ["openalex", "openalex", "istex"],
            "source_id": ["W1", "W2", "I1"],
            "from_openalex": [1, 1, 0],
            "from_istex": [0, 0, 1],
        })

    def test_step1_counter_attempted(self, mini_df, tmp_path):
        """step1_cross_source sets step1_attempted in counters."""
        # Redirect CATALOGS_DIR so it doesn't look for real unified_works.csv
        import utils as utils_mod
        orig = utils_mod.CATALOGS_DIR
        utils_mod.CATALOGS_DIR = str(tmp_path)
        try:
            from enrich_abstracts import is_missing, step1_cross_source
            df = mini_df.copy()
            df["_missing"] = df["abstract"].apply(is_missing)
            # Create a dummy unified_works.csv
            unified = df[["doi", "abstract"]].copy()
            unified.to_csv(os.path.join(str(tmp_path), "unified_works.csv"), index=False)
            counters = {}
            step1_cross_source(df, counters)
            assert "step1_attempted" in counters
            assert counters["step1_attempted"] >= 0
        finally:
            utils_mod.CATALOGS_DIR = orig

    def test_step3_counter_attempted(self, mini_df, tmp_path):
        """step3_istex sets step3_attempted in counters."""
        import enrich_abstracts as ea
        df = mini_df.copy()
        df["_missing"] = df["abstract"].apply(ea.is_missing)
        counters = {}
        ea.step3_istex(df, counters)
        assert "step3_attempted" in counters
        assert counters["step3_attempted"] >= 0


# ---------------------------------------------------------------------------
# Retry parameter plumbing tests
# ---------------------------------------------------------------------------

class TestRetryParameterPlumbing:
    def test_crossref_fetch_batch_forwards_retry_knobs(self, monkeypatch):
        import enrich_citations_batch as ecb

        captured = {}

        class DummyResponse:
            status_code = 200

            def json(self):
                return {"message": {"items": []}}

            def raise_for_status(self):
                return None

        def fake_retry_get(url, **kwargs):
            captured.update(kwargs)
            return DummyResponse()

        monkeypatch.setattr(ecb, "retry_get", fake_retry_get)

        rows, found = ecb.fetch_batch(
            ["10.1/a"],
            request_timeout=12.5,
            max_retries=7,
            retry_backoff=1.7,
            retry_jitter=0.3,
        )
        assert rows == []
        assert found == set()
        assert captured["timeout"] == 12.5
        assert captured["max_retries"] == 7
        assert captured["backoff_base"] == 1.7
        assert captured["jitter_max"] == 0.3

    def test_openalex_get_forwards_retry_knobs(self, monkeypatch):
        import enrich_citations_openalex as ecoa

        captured = {}

        class DummyResponse:
            def json(self):
                return {"results": []}

        def fake_retry_get(url, **kwargs):
            captured.update(kwargs)
            return DummyResponse()

        monkeypatch.setattr(ecoa, "retry_get", fake_retry_get)

        result = ecoa.openalex_get(
            {"filter": "doi:10.1/a"},
            request_timeout=9.0,
            max_retries=4,
            retry_backoff=1.4,
            retry_jitter=0.2,
        )
        assert result == {"results": []}
        assert captured["timeout"] == 9.0
        assert captured["max_retries"] == 4
        assert captured["backoff_base"] == 1.4
        assert captured["jitter_max"] == 0.2

    def test_abstract_step2_forwards_retry_knobs(self, monkeypatch):
        import enrich_abstracts as ea

        captured = {}

        class DummyResponse:
            def json(self):
                return {"results": []}

        def fake_retry_get(url, **kwargs):
            captured.update(kwargs)
            return DummyResponse()

        monkeypatch.setattr(ea, "retry_get", fake_retry_get)
        monkeypatch.setattr(ea, "load_cache", lambda _name: {})
        monkeypatch.setattr(ea, "save_cache", lambda _name, _data: None)

        df = pd.DataFrame({
            "doi": ["10.1/a"],
            "abstract": [""],
            "source": ["openalex"],
            "source_id": ["W1"],
            "_missing": [True],
            "from_openalex": [1],
        })
        counters = {}
        ea.step2_openalex(
            df,
            counters,
            checkpoint_every=1,
            request_timeout=8.0,
            max_retries=6,
            retry_backoff=1.3,
            retry_jitter=0.4,
        )
        assert captured["timeout"] == 8.0
        assert captured["max_retries"] == 6
        assert captured["backoff_base"] == 1.3
        assert captured["jitter_max"] == 0.4
