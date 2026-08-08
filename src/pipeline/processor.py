from __future__ import annotations

import logging
from datetime import datetime, timedelta

from pydantic import ValidationError

from pipeline.event import Event

logger = logging.getLogger(__name__)


class Processor:
    """Processes an event stream, maintaining per-product per-day counts.

    Each daily window stays open for **48 hours** after the day ends to
    capture late-arriving events.  Windows are closed when the latest
    event timestamp passes the boundary (midnight of ``date + 3 days``).

    Only *closed* windows appear in :attr:`summary` — in-flight dates
    whose 48-hour window is still open are held internally until they
    finalise.
    """

    def __init__(self) -> None:
        # Active counts — dates whose 48-hour window is still open.
        self._open: dict[str, dict[str, int]] = {}
        # Finalised counts — moved here once a daily window closes.
        self._finalized: dict[str, dict[str, int]] = {}
        # Maps each open date → its pre-computed deadline (midnight of date+3).
        self._open_dates: dict[str, datetime] = {}
        # O(1) lookup for already-closed dates.
        self._closed_dates: set[str] = set()
        # High-water mark: the latest event timestamp seen so far.
        self._latest_ts: datetime | None = None

    # ------------------------------------------------------------------
    # Public read-only properties
    # ------------------------------------------------------------------

    @property
    def summary(self) -> dict[str, dict[str, int]]:
        """Finalised counts: ``{product_id: {date: event_count}}``.

        Only includes dates whose 48-hour window has closed.  In-flight
        dates are *not* returned — use :attr:`open_summary` to inspect
        those.
        """
        return self._finalized

    @property
    def open_summary(self) -> dict[str, dict[str, int]]:
        """In-flight counts for dates whose windows are still open."""
        return self._open

    @property
    def latest_timestamp(self) -> datetime | None:
        """The most recent event timestamp processed, or ``None``."""
        return self._latest_ts

    @property
    def closed_dates(self) -> frozenset[str]:
        """Dates whose 48-hour windows have been closed."""
        return frozenset(self._closed_dates)

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process(self, events: list[dict], index: int) -> Event | None:
        """Validate and process the event at ``events[index]``.

        Args:
            events: A list of raw event dictionaries matching the input
                schema (``user_id``, ``product_id``, ``event_timestamp``,
                ``event_type``).
            index: The position in the list to process.

        Returns:
            The validated :class:`Event` if it was accepted, or ``None``
            if it was discarded (invalid schema or closed window).
        """
        # ---- schema validation --------------------------------------------
        try:
            event = Event(**events[index])
        except ValidationError:
            return None

        ts = datetime.fromisoformat(event.event_timestamp)
        date = ts.strftime("%Y-%m-%d")

        # ---- update the high-water mark & close expired windows -----------
        if self._latest_ts is None or ts > self._latest_ts:
            self._latest_ts = ts
            logger.debug(
                "Latest timestamp advanced to %s",
                self._latest_ts.isoformat(),
            )
            self._close_expired_windows()

        # ---- discard if the daily window has already closed ---------------
        if date in self._closed_dates:
            logger.debug(
                "Event discarded — window already closed for %s", date
            )
            return None

        # ---- register a new date & pre-compute its deadline ---------------
        if date not in self._open_dates:
            deadline = datetime.fromisoformat(date) + timedelta(days=3)
            # Edge case: first event for this date is already past the
            # deadline — close it immediately and discard.
            if self._latest_ts is not None and self._latest_ts >= deadline:
                self._closed_dates.add(date)
                logger.info(
                    "Date %s immediately closed — deadline %s already "
                    "past (latest: %s)",
                    date,
                    deadline.isoformat(),
                    self._latest_ts.isoformat(),
                )
                return None
            self._open_dates[date] = deadline
            logger.info(
                "New daily window opened for %s (deadline: %s)",
                date,
                deadline.isoformat(),
            )

        # ---- count the event (open window) --------------------------------
        self._open.setdefault(event.product_id, {})
        self._open[event.product_id][date] = (
            self._open[event.product_id].get(date, 0) + 1
        )

        return event

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def _close_expired_windows(self) -> None:
        """Close daily windows whose pre-computed deadline has passed.

        Only iterates :attr:`_open_dates` — not every product-date pair
        inside :attr:`_open` — so the scan stays cheap regardless of how
        many products or events have been accumulated.
        """
        assert self._latest_ts is not None

        for date, deadline in list(self._open_dates.items()):
            if self._latest_ts >= deadline:
                self._close_window(date)

    def _close_window(self, date: str) -> None:
        """Move all product counts for *date* from :attr:`_open` to
        :attr:`_finalized` and log the transition."""
        del self._open_dates[date]
        self._closed_dates.add(date)

        for product_id in list(self._open):
            product_dates = self._open[product_id]
            if date in product_dates:
                count = product_dates.pop(date)
                self._finalized.setdefault(product_id, {})[date] = count
                # Prune empty product entries to keep _open lean.
                if not product_dates:
                    del self._open[product_id]

        logger.info(
            "Daily window closed for %s (latest event: %s)",
            date,
            self._latest_ts.isoformat(),  # type: ignore[union-attr]
        )
