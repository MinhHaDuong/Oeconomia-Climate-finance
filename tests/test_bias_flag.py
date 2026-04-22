"""Test that compute_divergence.py accepts --no-equal-n flag.

RED: fails because --no-equal-n is not yet defined.
GREEN: passes after flag is added to the argparse parser.
"""

import os
import subprocess
import sys


def test_no_equal_n_flag_accepted(tmp_path):
    """compute_divergence.py must accept --no-equal-n flag without argparse error.

    Uses the smoke fixture to run a real (short) computation.
    Before the flag exists: argparse rejects it with 'unrecognized arguments',
    rc=2.  After the flag is added: the run either succeeds or fails for other
    reasons — but never with 'unrecognized arguments: --no-equal-n'.
    """
    smoke_dir = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
    script = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "compute_divergence.py"
    )
    out_csv = str(tmp_path / "tab_div_L1.csv")

    env = os.environ.copy()
    env["CLIMATE_FINANCE_DATA"] = smoke_dir

    result = subprocess.run(
        [
            sys.executable,
            script,
            "--method",
            "L1",
            "--output",
            out_csv,
            "--no-equal-n",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    # The flag must not be rejected by argparse.
    assert "unrecognized arguments: --no-equal-n" not in result.stderr, (
        f"Flag rejected by argparse.\nstderr: {result.stderr}"
    )
