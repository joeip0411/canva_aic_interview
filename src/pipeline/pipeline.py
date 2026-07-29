from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
