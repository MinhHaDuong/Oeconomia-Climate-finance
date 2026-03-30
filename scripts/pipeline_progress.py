"""Progress monitoring and enrichment priority utilities for the pipeline.

Exports
-------
EX_STUCK
    Exit code used when the watchdog detects a stuck pipeline (75, EX_TEMPFAIL).
WatchedProgress
    Rich progress bar with a background watchdog thread for stuck detection.
compute_priority_scores
    Return works_df with deterministic ``_priority`` score column.
sort_dois_by_priority
    Sort a list of DOIs by descending priority score.
"""

from typing import Any

import logging
import signal
import subprocess
import threading
import time
from collections.abc import Callable

import pandas as pd
from types import TracebackType

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

_log = logging.getLogger("pipeline.progress")

# Exit code for stuck-detection abort (EX_TEMPFAIL from sysexits.h)
EX_STUCK = 75


class WatchedProgress:
    """Rich progress bar with watchdog thread for stuck detection.

    Wraps ``rich.progress.Progress`` with:
    - Multi-task support, ETA column, throughput column
    - A daemon thread that checks each task's time-since-last-advance
    - If no advance for ``stuck_timeout`` seconds (default 300 = 5 min),
      fires ``notify-send``, calls ``flush_checkpoint``, and sets the
      ``on_stuck`` event (or raises SystemExit(75) if no event provided)
    - Registers a SIGTERM handler that flushes checkpoint before exit

    Parameters
    ----------
    stuck_timeout : float
        Seconds without progress before declaring stuck (default: 300).
    on_stuck : threading.Event | None
        If provided, set this event when stuck is detected instead of
        calling sys.exit(75). Useful for testing.
    flush_checkpoint : callable | None
        Called before exit on stuck detection or SIGTERM. Should save
        any in-progress work to disk.
    transient : bool
        If True, the progress display disappears after completion.
    disable : bool
        If True, disable the progress display (for non-TTY / CI).

    """

    def __init__(
        self,
        stuck_timeout: float = 300,
        on_stuck: threading.Event | None = None,
        flush_checkpoint: Callable[[], None] | None = None,
        transient: bool = False,
        disable: bool = False,
    ) -> None:
        self.stuck_timeout = stuck_timeout
        self.on_stuck = on_stuck
        self.flush_checkpoint = flush_checkpoint
        self._disable = disable

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=transient,
            disable=disable,
        )

        # Track last-advance time per task_id
        self._last_advance: dict[int, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._watchdog_thread: threading.Thread | None = None
        self._prev_sigterm: signal.Handlers = None  # type: ignore[assignment]

    def __enter__(self) -> "WatchedProgress":
        self._progress.__enter__()
        self._install_sigterm_handler()
        self._start_watchdog()
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        self._stop_event.set()
        if self._watchdog_thread is not None:
            self._watchdog_thread.join(timeout=2)
        self._restore_sigterm_handler()
        self._progress.__exit__(exc_type, exc_val, exc_tb)

    def add_task(self, description: str, total: int = 100, **kwargs: Any) -> TaskID:
        """Add a new task to the progress display."""
        task_id = self._progress.add_task(description, total=total, **kwargs)
        with self._lock:
            self._last_advance[task_id] = time.monotonic()
        return task_id

    def advance(self, task_id: TaskID, advance: float = 1) -> None:
        """Advance a task and reset its stuck timer."""
        self._progress.advance(task_id, advance)
        with self._lock:
            self._last_advance[task_id] = time.monotonic()

    def update(self, task_id: TaskID, **kwargs: Any) -> None:
        """Update task fields (description, total, etc.)."""
        self._progress.update(task_id, **kwargs)
        # If 'advance' or 'completed' changed, reset timer
        if "advance" in kwargs or "completed" in kwargs:
            with self._lock:
                self._last_advance[task_id] = time.monotonic()

    def _start_watchdog(self) -> None:
        """Launch daemon thread that polls for stuck tasks."""
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="progress-watchdog"
        )
        self._watchdog_thread.start()

    def _watchdog_loop(self) -> None:
        """Check every second if any task exceeded stuck_timeout."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=1.0)
            if self._stop_event.is_set():
                return
            now = time.monotonic()
            with self._lock:
                for task_id, last in self._last_advance.items():
                    if now - last > self.stuck_timeout:
                        self._handle_stuck(task_id)
                        return

    def _handle_stuck(self, task_id: int) -> None:
        """React to a stuck task: notify, flush, signal."""
        task = self._progress.tasks[task_id]
        msg = (
            f"Pipeline stuck: '{task.description}' has not advanced "
            f"for {self.stuck_timeout}s"
        )
        _log.warning(msg)

        # Desktop notification only when no programmatic handler is set
        if self.on_stuck is None:
            try:
                subprocess.run(
                    ["notify-send", "--urgency=critical", "Pipeline stuck", msg],
                    check=False,
                    timeout=5,
                )
            except FileNotFoundError:
                pass  # notify-send not installed

        # Flush checkpoint
        if self.flush_checkpoint is not None:
            try:
                self.flush_checkpoint()
            except Exception as exc:
                _log.warning("Checkpoint flush failed: %s", exc)

        # Signal stuck
        if self.on_stuck is not None:
            self.on_stuck.set()
        else:
            raise SystemExit(EX_STUCK)

    def _install_sigterm_handler(self) -> None:
        """Intercept SIGTERM to flush checkpoint before exit."""
        try:
            self._prev_sigterm = signal.getsignal(signal.SIGTERM)  # type: ignore[assignment]
            signal.signal(signal.SIGTERM, self._sigterm_handler)
        except (OSError, ValueError):
            pass  # not main thread or signal not available

    def _restore_sigterm_handler(self) -> None:
        """Restore previous SIGTERM handler."""
        try:
            if self._prev_sigterm is not None:
                signal.signal(signal.SIGTERM, self._prev_sigterm)
        except (OSError, ValueError):
            pass

    def _sigterm_handler(self, signum: int, frame: object) -> None:
        """Flush checkpoint on SIGTERM, then re-raise."""
        _log.info("SIGTERM received — flushing checkpoint before exit")
        if self.flush_checkpoint is not None:
            try:
                self.flush_checkpoint()
            except Exception as exc:
                _log.warning("Checkpoint flush on SIGTERM failed: %s", exc)
        raise SystemExit(128 + signum)


# ---------------------------------------------------------------------------
# Enrichment priority scoring
# ---------------------------------------------------------------------------

def compute_priority_scores(works_df: pd.DataFrame) -> pd.DataFrame:
    """Return works_df with a deterministic ``_priority`` score column and
    per-component ``_score_*`` columns (higher score = process first).

    Priority is based on:
    - ``_score_cited``   : raw ``cited_by_count`` (normalised: most-cited first)
    - ``_score_sources`` : ``source_count`` × 10  (multi-source works first)
    - ``_score_year``    : (year − 1990) × 0.01   (slight recency bonus)
    - ``_score_tiebreak``: stable MD5 hash of DOI  (fully deterministic)

    The function is pure: same input rows → same scores, regardless of row order.
    """
    import hashlib

    df = works_df.copy()

    cited = pd.to_numeric(df.get("cited_by_count", pd.Series(0, index=df.index)),
                          errors="coerce").fillna(0).clip(lower=0)

    sources = pd.to_numeric(df.get("source_count", pd.Series(1, index=df.index)),
                            errors="coerce").fillna(1).clip(lower=0)

    year = pd.to_numeric(df.get("year", pd.Series(1990, index=df.index)),
                         errors="coerce").fillna(1990)

    doi_str = df["doi"].fillna("").astype(str)
    tiebreak = doi_str.apply(
        lambda d: int(hashlib.md5(d.encode()).hexdigest(), 16) % 1_000_000 / 1_000_000
    )

    df["_score_cited"] = cited.values
    df["_score_sources"] = (sources * 10).values
    df["_score_year"] = ((year - 1990) * 0.01).values
    df["_score_tiebreak"] = tiebreak.values
    df["_priority"] = (
        df["_score_cited"] + df["_score_sources"] + df["_score_year"] + df["_score_tiebreak"]
    )

    return df


def sort_dois_by_priority(dois: list, works_df: pd.DataFrame) -> list:
    """Return *dois* sorted by descending priority score.

    DOIs absent from ``works_df`` are appended at the end (score = 0),
    preserving their relative insertion order for stability.

    Parameters
    ----------
    dois : list
        Normalised DOI strings to sort.
    works_df : DataFrame
        Works table with at minimum a ``doi`` column.

    Returns
    -------
    Sorted list of DOIs (highest priority first).

    """
    scored = compute_priority_scores(works_df)
    doi_to_priority = dict(zip(
        scored["doi"].fillna("").astype(str),
        scored["_priority"],
    ))
    return sorted(dois, key=lambda d: doi_to_priority.get(d, -1), reverse=True)
