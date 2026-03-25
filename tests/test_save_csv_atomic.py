"""Tests for #432: save_csv atomic write-then-rename pattern.

Verifies:
- save_csv writes to a temp file then renames atomically
- A crash mid-write leaves the original file intact
- Normal behavior preserved (file created, correct contents)
- No temp file remains after success or crash
"""

import os
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


class TestSaveCsvAtomic:
    def test_save_csv_creates_file(self, tmp_path):
        """Baseline: save_csv creates the target file with correct contents."""
        from utils import save_csv
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        path = str(tmp_path / "out.csv")
        save_csv(df, path)
        assert os.path.isfile(path)
        loaded = pd.read_csv(path)
        assert list(loaded.columns) == ["a", "b"]
        assert len(loaded) == 2

    def test_save_csv_atomic_on_crash(self, tmp_path, monkeypatch):
        """A crash mid-write leaves the original file intact.

        We simulate a crash by patching DataFrame.to_csv to corrupt the
        temp file (write garbage then raise). Because save_csv must write
        to a TEMP file (not the target), the rename never happens and the
        original target is untouched.

        With the old non-atomic implementation (writing directly to target),
        this test would catch that the target is corrupted/absent.
        """
        from utils import save_csv

        # Write initial "original" data to the target path.
        original_df = pd.DataFrame({"col": ["original_data"]})
        target = str(tmp_path / "data.csv")
        original_df.to_csv(target, index=False, encoding="utf-8")
        original_content = open(target, encoding="utf-8").read()

        real_to_csv = pd.DataFrame.to_csv

        def crash_during_write(self_df, path_or_buf, **kwargs):
            # Write corrupted/partial data to whatever file we're given,
            # then crash — simulates a mid-write failure.
            with open(path_or_buf, "w", encoding="utf-8") as fh:
                fh.write("CORRUPTED PARTIAL DATA\n")
            raise OSError("Simulated crash during write")

        monkeypatch.setattr(pd.DataFrame, "to_csv", crash_during_write)

        new_df = pd.DataFrame({"col": ["new_data"]})
        with pytest.raises(OSError, match="Simulated crash during write"):
            save_csv(new_df, target)

        # The original file must be untouched.
        assert os.path.isfile(target), "Original file must still exist after crash"
        assert open(target, encoding="utf-8").read() == original_content, (
            "Original file contents must not be modified after a crash mid-write. "
            "save_csv must use write-then-rename (atomic) pattern."
        )

    def test_save_csv_no_temp_file_left_on_success(self, tmp_path):
        """No temporary file is left behind after a successful save."""
        from utils import save_csv
        df = pd.DataFrame({"x": [1]})
        target = str(tmp_path / "result.csv")
        save_csv(df, target)
        files = os.listdir(str(tmp_path))
        assert files == ["result.csv"], (
            f"Unexpected files left in directory: {files}"
        )

    def test_save_csv_no_temp_file_left_on_crash(self, tmp_path, monkeypatch):
        """No temporary file is left behind after a crash."""
        from utils import save_csv

        original_df = pd.DataFrame({"col": ["original"]})
        target = str(tmp_path / "data.csv")
        original_df.to_csv(target, index=False, encoding="utf-8")

        def crash_during_write(self_df, path_or_buf, **kwargs):
            with open(path_or_buf, "w", encoding="utf-8") as fh:
                fh.write("CORRUPTED\n")
            raise OSError("Simulated crash")

        monkeypatch.setattr(pd.DataFrame, "to_csv", crash_during_write)

        new_df = pd.DataFrame({"col": ["new"]})
        with pytest.raises(OSError):
            save_csv(new_df, target)

        files = os.listdir(str(tmp_path))
        assert files == ["data.csv"], (
            f"Temp file left behind after crash: {files}"
        )
