from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime as dt
from datetime import timedelta

from src.pipeline.event import Event


class StreamProcessor:
    """Processes a stream of Event objects and computes daily active users.

    Valid events are bucketed by calendar date. Duplicate user_ids within
    the same day are counted only once. A day is *closed* (finalized) once
    the latest seen timestamp is at least 24 hours past midnight of that
    day. Call ``flush_results()`` to retrieve finalized counts and free
    memory.
    """

    def __init__(self) -> None:
        self._daily_users: dict[str, set[str]] = defaultdict(set)
        self._results: dict[str, int] = {}
        self._max_ts: dt | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, events: Iterable[Event]) -> None:
        """Ingest a batch of *events* and accumulate daily active users.

        Each event's date is derived from its ``timestamp`` property.
        Duplicate ``user_id`` values within the same calendar day are
        counted only once. Stale days are finalized automatically.
        """
        for event in events:
            day = event.timestamp.date().isoformat()
            self._daily_users[day].add(event.user_id)
            if self._max_ts is None or event.timestamp > self._max_ts:
                self._max_ts = event.timestamp
                self._close_stale_days()

    def flush_results(self) -> dict[str, int]:
        """Return finalized daily active-user counts and clear the store.

        Only days that have been *closed* (24+ hours past their end) are
        returned. Days still receiving events remain in the processor.
        """
        results = dict(self._results)
        self._results.clear()
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _close_stale_days(self) -> None:
        """Finalize any day whose midnight is 24+ hours behind ``_max_ts``."""
        if self._max_ts is None:
            return
        stale = [
            day
            for day in self._daily_users
            if self._max_ts >= dt.fromisoformat(day) + timedelta(hours=24)
        ]
        for day in stale:
            self._results[day] = len(self._daily_users.pop(day))
