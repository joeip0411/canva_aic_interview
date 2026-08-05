import logging
from datetime import datetime, timedelta
from typing import Any

from .event import Event

logger = logging.getLogger(__name__)


class Processor:
    """Processes a stream of user-interaction events and computes daily metrics.

    Orchestrates the pipeline: validation → processing → output.
    """

    def __init__(self) -> None:
        """Initialize the processor with empty state."""
        # Open windows: {date: {user_id: count}}
        self._daily_counts: dict[str, dict[str, int]] = {}
        # Closed windows: {date: {user_id: count}}
        self._result: dict[str, dict[str, int]] = {}

    @property
    def daily_counts(self) -> dict[str, dict[str, int]]:
        """Return the currently open daily event counts per user.

        Shape matches the output schema: {date: {user_id: count}}.
        """
        return self._daily_counts

    @property
    def result(self) -> dict[str, dict[str, int]]:
        """Return the finalized (closed-window) daily event counts per user.

        Once a date is in result, its counts are immutable.
        """
        return self._result

    def process(self, stream: list[dict[str, Any]], idx: int) -> Event | None:
        """Extract, validate, and count a single record from the stream buffer.

        Args:
            stream: A list of raw event dictionaries representing the stream buffer.
            idx: The position of the record to process within the stream.

        Returns:
            A validated Event object, or None if the event was discarded
            or if validation/indexing failed.
        """
        try:
            raw_event = stream[idx]
        except IndexError:
            logger.warning(
                "Stream index %d is out of bounds for stream of length %d",
                idx,
                len(stream),
            )
            return None
        logger.debug("Processing record at index %d", idx)
        event = self._validate(raw_event)
        if event is None:
            return None

        # Extract the date portion from the ISO 8601 timestamp (e.g. "2026-08-05")
        event_date = event.event_timestamp[:10]

        if self._is_discarded(event_date, event.user_id):
            return None

        self._increment_count(event_date, event.user_id)

        # Close any date window that is now at least 24 hours behind
        self._close_windows(event.event_timestamp)

        return event

    def _close_windows(self, event_timestamp: str) -> None:
        """Close the counting window if this event is at least 24 hours past a date.

        Computes the date that is exactly 24 hours before the event timestamp.
        If that date has an open window in _daily_counts, it is moved to _result.

        Per the spec: "Close the window for a particular day if the a new event
        received is at least 24 hours after the date."
        """
        event_dt = datetime.fromisoformat(event_timestamp)

        # The date whose midnight is 24 hours (or more) before this event
        threshold_dt = event_dt - timedelta(hours=24)
        stale_date = threshold_dt.strftime("%Y-%m-%d")

        if stale_date in self._daily_counts:
            self._result[stale_date] = self._daily_counts.pop(stale_date)
            logger.info(
                "Closed window for date=%s (event at %s is >= 24h after midnight)",
                stale_date,
                event_timestamp,
            )

    def _increment_count(self, event_date: str, user_id: str) -> None:
        """Increment the event count for a user on a given date."""
        self._daily_counts.setdefault(event_date, {})
        self._daily_counts[event_date][user_id] = (
            self._daily_counts[event_date].get(user_id, 0) + 1
        )
        logger.debug(
            "Updated daily counts: date=%s user_id=%s count=%d",
            event_date,
            user_id,
            self._daily_counts[event_date][user_id],
        )

    def _is_discarded(self, event_date: str, user_id: str) -> bool:
        """Return True if the event's date window has already been closed.

        Performs an O(1) lookup against the _result dict keys.
        """
        if event_date in self._result:
            logger.info(
                "Discarding event: date=%s is already closed (user_id=%s)",
                event_date,
                user_id,
            )
            return True
        return False

    def _validate(self, raw_event: dict[str, Any]) -> Event | None:
        """Validate a raw input dictionary and return a structured Event.

        Returns None if validation fails, so the caller can skip the event
        without crashing the pipeline.
        """
        logger.debug("Validating raw event: %s", raw_event)
        try:
            event = Event.model_validate(raw_event)
        except (TypeError, ValueError) as exc:
            logger.warning("Validation failed for event: %s", exc)
            return None
        logger.debug("Event validated successfully: user_id=%s", event.user_id)
        return event
