from pathlib import Path

SNAPSHOT_DATE = "2026-03-26"


def test_date_in_companion_paper():
    text = Path("content/companion-paper.qmd").read_text()
    assert SNAPSHOT_DATE in text, (
        f"Snapshot date {SNAPSHOT_DATE} not found in companion-paper.qmd"
    )


def test_date_in_data_paper():
    text = Path("content/data-paper.qmd").read_text()
    assert SNAPSHOT_DATE in text, (
        f"Snapshot date {SNAPSHOT_DATE} not found in data-paper.qmd"
    )
