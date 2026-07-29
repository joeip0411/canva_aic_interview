import logging
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


class Event(BaseModel):
    """A single raw event from the workspace action stream (§2.1)."""

    user_id: str
    workspace_id: str
    action: str
    event_timestamp: str
    metadata: dict

    @field_validator("event_timestamp")
    @classmethod
    def _validate_iso8601_utc(cls, v: str) -> str:
        """Ensure the timestamp is a valid ISO-8601 UTC datetime (§7.4)."""
        try:
            dt = datetime.fromisoformat(v)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid ISO-8601 timestamp: {v!r}") from exc

        if dt.tzinfo is None:
            raise ValueError(f"Timestamp must be UTC-aware, got naive datetime: {v!r}")

        if dt.tzinfo != UTC:
            raise ValueError(f"Timestamp must be in UTC, got {dt.tzinfo}: {v!r}")

        return v


SESSION_GAP_DAYS: int = 30


class Aggregator:
    """Ingests a stream of Event objects, tracks sessions per workspace (§3),
    and emits summary dicts when a session terminates.
    """

    def __init__(self) -> None:
        # Internal state per active workspace:
        #   workspace_id -> {
        #       "user_ids": set[str],
        #       "action_count": int,
        #       "pro_subscription_count": int,
        #       "latest_ts": datetime,
        #   }
        self._active: dict[str, dict] = {}
        # Workspace IDs whose sessions have already been terminated.
        self._terminated: set[str] = set()

    # -- Public API ---------------------------------------------------------

    def process(self, events: list[Event]) -> Generator[dict, None, None]:
        """Process a batch of events in stream order.

        Yields summary dicts as sessions terminate.  Each dict has the keys
        ``workspace_id``, ``user_count``, ``action_count``, and
        ``pro_subscription_count``.
        """
        for event in events:
            wid = event.workspace_id

            if wid in self._terminated:
                logger.warning(
                    "Event for already-terminated workspace %s ignored.", wid
                )
                continue

            event_ts = datetime.fromisoformat(event.event_timestamp)

            if wid not in self._active:
                self._init_session(wid, event_ts)

            state = self._active[wid]
            gap = event_ts - state["latest_ts"]

            if gap > timedelta(days=SESSION_GAP_DAYS):
                yield self._terminate_session(wid, state, gap)
                continue

            self._update_state(state, event, event_ts)

    # -- Session lifecycle ---------------------------------------------------

    def _init_session(self, workspace_id: str, timestamp: datetime) -> None:
        """Create session state for a new workspace."""
        self._active[workspace_id] = {
            "user_ids": set(),
            "action_count": 0,
            "pro_subscription_count": 0,
            "latest_ts": timestamp,
        }
        logger.info("Session started for workspace %s.", workspace_id)

    def _terminate_session(
        self, workspace_id: str, state: dict, gap: timedelta
    ) -> dict:
        """Freeze the workspace, remove from active tracking, and return its summary dict."""
        summary = self._build_summary(workspace_id, state)
        self._terminated.add(workspace_id)
        del self._active[workspace_id]
        logger.info(
            "Session terminated for workspace %s (gap %s > %s days).",
            workspace_id, gap, SESSION_GAP_DAYS,
        )
        return summary

    # -- Internal helpers ----------------------------------------------------

    @staticmethod
    def _update_state(state: dict, event: Event, event_ts: datetime) -> None:
        """Apply a single event to the running session state."""
        state["user_ids"].add(event.user_id)
        state["action_count"] += 1
        if event.action == "purchase_pro_subscription":
            state["pro_subscription_count"] += 1
        state["latest_ts"] = max(event_ts, state["latest_ts"])

    @staticmethod
    def _build_summary(workspace_id: str, state: dict) -> dict:
        """Build a summary dict from a terminated session's state."""
        return {
            "workspace_id": workspace_id,
            "user_count": len(state["user_ids"]),
            "action_count": state["action_count"],
            "pro_subscription_count": state["pro_subscription_count"],
        }
