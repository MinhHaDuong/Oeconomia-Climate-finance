"""Shared test helpers for the divergence pipeline tests."""

import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
GOLDEN_DIR = os.path.join(FIXTURES_DIR, "golden")

sys.path.insert(0, SCRIPTS_DIR)


def smoke_env():
    """Environment that redirects pipeline_loaders to fixture data."""
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": FIXTURES_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
    }


def run_compute(method, output_path, timeout=300):
    """Run compute_divergence.py --method M --output P."""
    return subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "compute_divergence.py"),
            "--method", method,
            "--output", str(output_path),
        ],
        env=smoke_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
