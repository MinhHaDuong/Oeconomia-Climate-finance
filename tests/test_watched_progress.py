"""Tests for WatchedProgress context manager — stuck detection and checkpoint flush."""

import os
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.integration

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def test_watched_progress_stuck_detection():
    """Watchdog fires when no advance happens within stuck_timeout.

    Setup: WatchedProgress with stuck_timeout=2s.
    Action: start a task, advance once, then sleep 3s without advancing.
    Assert:
      - The stuck event is set (watchdog detected the stall).
      - The checkpoint flush callback was invoked before exit.
    """
    from utils import WatchedProgress

    flushed = threading.Event()

    def flush_checkpoint():
        flushed.set()

    stuck_fired = threading.Event()

    with WatchedProgress(
        stuck_timeout=2,
        on_stuck=stuck_fired,
        flush_checkpoint=flush_checkpoint,
    ) as wp:
        task = wp.add_task("test-task", total=10)
        wp.advance(task, 1)
        # Wait long enough for watchdog to detect stuck
        time.sleep(3.5)

    assert stuck_fired.is_set(), "Watchdog should have detected stuck task"
    assert flushed.is_set(), "Checkpoint flush callback should have been invoked"


def test_watched_progress_no_false_alarm():
    """Watchdog does NOT fire when tasks advance regularly.

    Keep advancing every 0.5s for 3s with a 2s stuck_timeout.
    The stuck event should never be set.
    """
    from utils import WatchedProgress

    stuck_fired = threading.Event()

    with WatchedProgress(
        stuck_timeout=2,
        on_stuck=stuck_fired,
    ) as wp:
        task = wp.add_task("regular-task", total=20)
        for _ in range(6):
            wp.advance(task, 1)
            time.sleep(0.5)

    assert not stuck_fired.is_set(), "Watchdog should not fire when tasks advance regularly"


def test_watched_progress_multi_task():
    """Watchdog monitors ALL tasks — one stuck task triggers the alarm."""
    from utils import WatchedProgress

    stuck_fired = threading.Event()
    flushed = threading.Event()

    with WatchedProgress(
        stuck_timeout=2,
        on_stuck=stuck_fired,
        flush_checkpoint=flushed.set,
    ) as wp:
        task_a = wp.add_task("active-task", total=20)
        task_b = wp.add_task("stuck-task", total=10)  # noqa: F841
        # Only advance task_a, leave task_b stuck
        for _ in range(4):
            wp.advance(task_a, 1)
            time.sleep(1)

    assert stuck_fired.is_set(), "Watchdog should detect the stuck task"
