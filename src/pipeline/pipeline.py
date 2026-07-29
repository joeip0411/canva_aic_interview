import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants — extracted so they can be changed in one place.
# ------------------------------------------------------------------

_SESSION_TIMEOUT_MINUTES = 30
_AI_EVENT_TYPE = "use_ai_magic"


# ==================================================================
# Shared timestamp helpers
#
# Extracted to module level so both RawEventData (input) and
# OutputSummaryData (output) can reuse the same validation logic.
# Each helper does exactly one thing.
# ==================================================================


def _normalise_iso8601_string(value: str) -> str:
    """Replace the 'Z' UTC suffix with '+00:00' so fromisoformat can parse it."""
    return value.replace("Z", "+00:00")


def _parse_to_datetime(normalised: str) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware datetime.

    Raises ValueError if the string is not a valid ISO-8601 datetime.
    """
    try:
        return datetime.fromisoformat(normalised)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"timestamp must be a valid ISO-8601 string, got: {normalised!r}"
        ) from exc


def _ensure_utc(parsed: datetime, original: str) -> None:
    """Raise ValueError if the datetime is not in UTC.

    Checks two conditions separately so the error message pinpoints the issue:
    1. A timezone offset must be present.
    2. That offset must be UTC (+00:00 or Z).
    """
    if parsed.tzinfo is None:
        raise ValueError(
            f"timestamp must include a timezone offset, got: {original!r}"
        )
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError(
            f"timestamp must be UTC, got offset {parsed.utcoffset()} in: {original!r}"
        )


def _validate_iso8601_utc(value: str) -> str:
    """Full validation pipeline for an ISO-8601 UTC timestamp string.

    Returns the stripped value on success. This is the single entry point
    that field_validators delegate to.
    """
    stripped = value.strip()
    normalised = _normalise_iso8601_string(stripped)
    parsed = _parse_to_datetime(normalised)
    _ensure_utc(parsed, stripped)
    return stripped


# ==================================================================
# Input model
# ==================================================================


class RawEventData(BaseModel):
    """Validates each incoming raw event against the input schema.

    All fields are required. Timestamps must be ISO-8601 UTC strings.
    The meta field accepts arbitrary key-value pairs and may be empty.
    """

    user_id: str = Field(..., min_length=1, description="Non-empty user identifier")
    timestamp: str = Field(
        ...,
        min_length=1,
        description="ISO-8601 UTC timestamp, e.g. 2026-03-01T10:00:00Z",
    )
    event_type: str = Field(
        ..., min_length=1, description="Non-empty snake_case event identifier"
    )
    meta: dict[str, object] = Field(
        default_factory=dict,
        description="Arbitrary key-value pairs; defaults to empty dict",
    )

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_blank(cls, value: str) -> str:
        """Reject user_id that is empty or whitespace-only."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("user_id must not be empty or whitespace-only")
        return stripped

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_valid_iso8601_utc(cls, value: str) -> str:
        """Validate that the timestamp is a well-formed ISO-8601 UTC string."""
        return _validate_iso8601_utc(value)

    @field_validator("event_type")
    @classmethod
    def event_type_must_not_be_blank(cls, value: str) -> str:
        """Reject event_type that is empty or whitespace-only."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("event_type must not be empty or whitespace-only")
        return stripped


# ==================================================================
# Output model
# ==================================================================


class OutputSummaryData(BaseModel):
    """Validates each session-summary record against the output schema.

    All fields are required. session_start and session_end are ISO-8601 UTC
    timestamps. total_events must be a positive integer.
    """

    session_id: str = Field(
        ...,
        min_length=1,
        description='Unique session identifier: "{user_id}{session_start}{session_end}"',
    )
    user_id: str = Field(
        ..., min_length=1, description="The user this session belongs to"
    )
    session_start: str = Field(
        ...,
        min_length=1,
        description="ISO-8601 UTC timestamp of the first event in the session",
    )
    session_end: str = Field(
        ...,
        min_length=1,
        description="ISO-8601 UTC timestamp of the last event in the session",
    )
    total_events: int = Field(
        ..., gt=0, description="Number of events in this session"
    )
    is_ai_enhanced: bool = Field(
        ...,
        description="True if at least one event in the session has event_type == 'use_ai_magic'",
    )

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_blank(cls, value: str) -> str:
        """Reject user_id that is empty or whitespace-only."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("user_id must not be empty or whitespace-only")
        return stripped

    @field_validator("session_start")
    @classmethod
    def session_start_must_be_valid_iso8601_utc(cls, value: str) -> str:
        """Validate that session_start is a well-formed ISO-8601 UTC string."""
        return _validate_iso8601_utc(value)

    @field_validator("session_end")
    @classmethod
    def session_end_must_be_valid_iso8601_utc(cls, value: str) -> str:
        """Validate that session_end is a well-formed ISO-8601 UTC string."""
        return _validate_iso8601_utc(value)


# ==================================================================
# Session state tracker
# ==================================================================


@dataclass
class _SessionState:
    """Internal tracker for a single in-progress user session.

    Stores only the metadata needed to decide session boundaries and
    build the final :class:`OutputSummaryData` — not the full event list.
    This keeps memory bounded regardless of session length.
    """

    session_start: str
    last_timestamp: str
    total_events: int
    is_ai_enhanced: bool


# ==================================================================
# Gap-comparison helpers
#
# Used by StreamProcessor for both stale-event checks and session
# boundary decisions.  Each helper does exactly one thing.
# ==================================================================


def _to_datetime(iso_string: str) -> datetime:
    """Convert a validated ISO-8601 UTC string to a timezone-aware datetime."""
    normalised = _normalise_iso8601_string(iso_string)
    return _parse_to_datetime(normalised)


def _gap_exceeds_timeout(earlier: datetime, later: datetime) -> bool:
    """Return ``True`` if the gap between two datetimes exceeds the session timeout."""
    return (later - earlier) > timedelta(minutes=_SESSION_TIMEOUT_MINUTES)


# ==================================================================
# Stream processor
# ==================================================================


class StreamProcessor:
    """Transforms a stream of raw event dicts into session summaries.

    Accepts an iterable of raw event dicts, validates each one, discards
    stale events, groups the remainder into per-user sessions based on a
    30-minute inactivity gap, and yields :class:`OutputSummaryData` records
    as sessions are completed.
    """

    def __init__(self) -> None:
        """Initialise the processor with empty per-user session state."""
        self._open_sessions: dict[str, _SessionState] = {}

    def process(self, events: Iterable[dict[str, object]]) -> Iterator[OutputSummaryData]:
        """Process a stream of raw events and yield completed session summaries.

        Sessions are yielded as soon as they are closed — either because a
        new event for the same user arrived after > 30 minutes of inactivity,
        or because the input stream was exhausted.
        """
        for raw in events:
            validated = self._validate_event(raw)
            if validated is None:
                continue

            if self._is_stale(validated):
                logger.info(
                    "Stale event discarded — user_id=%s timestamp=%s",
                    validated.user_id,
                    validated.timestamp,
                )
                continue

            # This event may close a previous session and start a new one.
            yield from self._ingest_event(validated)

        # End of stream — close every still-open session.
        yield from self._flush_all()

    @staticmethod
    def _validate_event(raw: dict[str, object]) -> RawEventData | None:
        """Validate a raw dict into a :class:`RawEventData`.

        Returns ``None`` if validation fails, logging a warning with the
        invalid input so the caller can debug data-quality issues.
        """
        try:
            return RawEventData(**raw)
        except Exception:
            logger.warning("Invalid event skipped: %s", raw, exc_info=True)
            return None

    @staticmethod
    def _is_stale(event: RawEventData) -> bool:
        """Return ``True`` if the event timestamp is more than 30 minutes old."""
        event_time = _to_datetime(event.timestamp)
        now = datetime.now(timezone.utc)
        return _gap_exceeds_timeout(event_time, now)

    def _start_session(self, event: RawEventData) -> None:
        """Create a new in-progress session seeded with *event*."""
        self._open_sessions[event.user_id] = _SessionState(
            session_start=event.timestamp,
            last_timestamp=event.timestamp,
            total_events=1,
            is_ai_enhanced=(event.event_type == _AI_EVENT_TYPE),
        )

    def _ingest_event(self, event: RawEventData) -> Iterator[OutputSummaryData]:
        """Add an event to its user's current session.

        If the gap between this event and the user's previous session exceeds
        the session timeout, the previous session is closed and yielded before
        this event starts a new one.
        """
        user_id = event.user_id
        current = self._open_sessions.get(user_id)

        if current is None:
            # No open session for this user — start a fresh one.
            self._start_session(event)
            return

        # Compare this event's timestamp against the session's last timestamp.
        last_time = _to_datetime(current.last_timestamp)
        this_time = _to_datetime(event.timestamp)

        if _gap_exceeds_timeout(last_time, this_time):
            # Inactivity threshold exceeded — close old session, start new one.
            yield from self._close_session(user_id)
            self._start_session(event)
            logger.info(
                "New session started — user_id=%s timestamp=%s "
                "(gap exceeded %d min threshold)",
                user_id,
                event.timestamp,
                _SESSION_TIMEOUT_MINUTES,
            )
        else:
            # Within the same session — update the running state.
            current.last_timestamp = event.timestamp
            current.total_events += 1
            if event.event_type == _AI_EVENT_TYPE:
                current.is_ai_enhanced = True

    def _flush_all(self) -> Iterator[OutputSummaryData]:
        """Close and yield every remaining open session.

        Called once at the end of the input stream so no sessions are lost.
        """
        # Snapshot the keys so we can mutate the dict during iteration.
        for user_id in list(self._open_sessions):
            yield from self._close_session(user_id)

    def _close_session(self, user_id: str) -> Iterator[OutputSummaryData]:
        """Build and yield an :class:`OutputSummaryData` from the user's open session.

        Removes the session from ``_open_sessions`` so the user can start a fresh one.
        """
        state = self._open_sessions.pop(user_id, None)
        if state is None:
            return

        session_id = f"{user_id}{state.session_start}{state.last_timestamp}"

        summary = OutputSummaryData(
            session_id=session_id,
            user_id=user_id,
            session_start=state.session_start,
            session_end=state.last_timestamp,
            total_events=state.total_events,
            is_ai_enhanced=state.is_ai_enhanced,
        )

        logger.info(
            "Session closed — id=%s user_id=%s events=%d ai=%s",
            session_id,
            user_id,
            state.total_events,
            state.is_ai_enhanced,
        )

        yield summary
