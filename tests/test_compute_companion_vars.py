"""Unit tests for scripts/compute_companion_vars.py (ticket 0064).

Covers the pure-Python helpers; end-to-end resolution/fig checks belong in
test_companion_vars_resolved.py.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from compute_companion_vars import _contiguous_runs


@pytest.mark.parametrize(
    "years, expected",
    [
        ([], []),
        ([2006], [[2006, 2006]]),
        (
            [2001, 2002, 2006, 2012, 2013, 2014, 2015],
            [[2001, 2002], [2006, 2006], [2012, 2015]],
        ),
    ],
)
def test_contiguous_runs(years, expected):
    assert _contiguous_runs(years) == expected
