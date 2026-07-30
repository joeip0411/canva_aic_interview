"""Core stream-processing logic for asset engagement scoring."""

import logging
from calendar import monthrange
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from src.pipeline.schema import Event

logger = logging.getLogger(__name__)

#: Number of calendar months an asset is tracked from its creation date
#: (the creation month itself counts as month 1).
TRACKING_WINDOW_MONTHS = 3


class Processor:
    """Stream processor that calculates per-asset engagement scores.

    Asset creation dates are inferred from the event stream: every asset
    must have at least one ``event_type == "asset_creation"`` event whose
    ``event_time`` is used as the creation date.  Creation events are not
    counted toward engagement metrics.
    """

    def __init__(self) -> None:
        # Per-asset running state — keyed by asset_id.
        self._results: dict[str, dict] = defaultdict(
            lambda: {"creator_id": "", "unique_users": set(), "total_usage_count": 0}
        )
        # Inferred asset creation datetimes (from asset_creation events).
        self._creation_dates: dict[str, datetime] = {}

        # Summary counters.
        self._valid_count = 0
        self._skipped_window_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, events: Iterable[Event]) -> dict[str, dict]:
        """Process a stream of :class:`Event` objects and return per-asset scores.

        Parameters
        ----------
        events:
            An iterable of :class:`Event` objects.  Every asset must have
            at least one ``asset_creation`` event to infer its creation date.

        Returns
        -------
        dict
            Mapping of ``asset_id`` to::

                {
                    "asset_id": str,
                    "creator_id": str,
                    "unique_user_count": int,
                    "total_usage_count": int,
                }
        """
        logger.info("Processor started — beginning event stream ingestion.")

        self._reset()

        for event in events:
            self._ingest_one(event)

        logger.info(
            "Processor finished — valid=%d, skipped_window=%d, assets_scored=%d.",
            self._valid_count,
            self._skipped_window_count,
            len(self._results),
        )

        return self._build_output()

    # ------------------------------------------------------------------
    # Per-event ingestion (orchestrator)
    # ------------------------------------------------------------------

    def _ingest_one(self, event: Event) -> None:
        """Route a single validated event through the pipeline."""
        if self._capture_creation_date(event):
            return

        if not self._within_tracking_window(event):
            return

        self._aggregate(event)

    # ------------------------------------------------------------------
    # Individual concerns
    # ------------------------------------------------------------------

    def _capture_creation_date(self, event: Event) -> bool:
        """Store creation date if *event* is an ``asset_creation`` event.

        Returns ``True`` when the event was a creation event (so the
        caller knows to skip aggregation), ``False`` otherwise.
        """
        if event.event_type != "asset_creation":
            return False

        self._creation_dates[event.asset_id] = datetime.fromisoformat(
            event.event_time
        )
        return True

    def _within_tracking_window(self, event: Event) -> bool:
        """Return ``True`` if *event* falls within the asset's 3‑month window.

        The window extends from the creation date (inclusive) to exactly
        3 calendar months later (inclusive, end of that day).  The creation
        month counts as month 1.

        When the creation date is not yet known the event is allowed
        through (first-pass tolerance).
        """
        creation = self._creation_dates.get(event.asset_id)
        if creation is None:
            return True

        event_dt = datetime.fromisoformat(event.event_time)

        # Add TRACKING_WINDOW_MONTHS to the creation date.
        window_end_month = creation.month + TRACKING_WINDOW_MONTHS
        window_end_year = creation.year + (window_end_month - 1) // 12
        window_end_month = ((window_end_month - 1) % 12) + 1

        # Clamp day when the target month is shorter (e.g. Jan 31 → Apr 30).
        _, last_day = monthrange(window_end_year, window_end_month)
        window_end_day = min(creation.day, last_day)

        window_end = datetime(
            window_end_year, window_end_month, window_end_day, 23, 59, 59
        )

        return event_dt <= window_end

    def _aggregate(self, event: Event) -> None:
        """Increment engagement counters for *event*'s asset."""
        self._valid_count += 1

        asset = self._results[event.asset_id]
        asset["creator_id"] = event.creator_id
        asset["unique_users"].add(event.user_id)
        asset["total_usage_count"] += 1

    def _reset(self) -> None:
        """Clear internal state so the processor can be reused."""
        self._results.clear()
        self._creation_dates.clear()
        self._valid_count = 0
        self._skipped_window_count = 0

    def _build_output(self) -> dict[str, dict]:
        """Convert internal accumulators to the output schema."""
        return {
            asset_id: {
                "asset_id": asset_id,
                "creator_id": data["creator_id"],
                "unique_user_count": len(data["unique_users"]),
                "total_usage_count": data["total_usage_count"],
            }
            for asset_id, data in self._results.items()
        }
