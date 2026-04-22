"""Tests for the --no-equal-n flag on compute_divergence.py.

test_no_equal_n_flag_accepted: checks that argparse accepts the flag.
test_bias_flag_produces_different_output: checks that the flag changes values.
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


def test_bias_flag_produces_different_output(tmp_path):
    """--no-equal-n and default equal_n produce different divergence values.

    Uses the smoke fixture (100 works, unequal year distribution: few papers
    in early years, many in late years).  S2_energy is sample-size-sensitive:
    energy distance depends on the actual vectors used, not just their mean,
    so subsampling the larger window to match the smaller one changes the
    statistic.  L1 (JS on mean TF-IDF) is not sensitive enough for this check.

    The test asserts mean(value) differs between runs, confirming that the
    flag propagates to the private computation module.
    """
    smoke_dir = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
    script = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "compute_divergence.py"
    )
    out_equal = str(tmp_path / "tab_div_equal.csv")
    out_unequal = str(tmp_path / "tab_div_unequal.csv")

    env = os.environ.copy()
    env["CLIMATE_FINANCE_DATA"] = smoke_dir

    base_cmd = [sys.executable, script, "--method", "S2_energy"]

    # Run with equal_n=True (config default, no flag)
    r_equal = subprocess.run(
        base_cmd + ["--output", out_equal],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_equal.returncode == 0, f"equal_n run failed:\n{r_equal.stderr}"

    # Run with equal_n=False (--no-equal-n override)
    r_unequal = subprocess.run(
        base_cmd + ["--output", out_unequal, "--no-equal-n"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r_unequal.returncode == 0, f"--no-equal-n run failed:\n{r_unequal.stderr}"

    import pandas as pd

    df_equal = pd.read_csv(out_equal)
    df_unequal = pd.read_csv(out_unequal)

    mean_equal = df_equal["value"].mean()
    mean_unequal = df_unequal["value"].mean()

    assert abs(mean_equal - mean_unequal) > 1e-6, (
        f"--no-equal-n had no effect on S2_energy output: "
        f"mean_equal={mean_equal:.6f}, mean_unequal={mean_unequal:.6f}"
    )
