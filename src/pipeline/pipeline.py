from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    event_type: str = Field(..., min_length=1, description="Non-empty snake_case event identifier")
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

    # ------------------------------------------------------------------
    # Timestamp validation — broken into single-purpose helpers so each
    # method does exactly one thing.
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_iso8601_string(value: str) -> str:
        """Replace the 'Z' UTC suffix with '+00:00' so fromisoformat can parse it."""
        return value.replace("Z", "+00:00")

    @staticmethod
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

    @staticmethod
    def _ensure_utc(parsed: datetime, original: str) -> None:
        """Raise ValueError if the datetime is not in UTC."""
        if parsed.tzinfo is None:
            raise ValueError(
                f"timestamp must include a timezone offset, got: {original!r}"
            )
        if parsed.utcoffset().total_seconds() != 0:
            raise ValueError(
                f"timestamp must be UTC, got offset {parsed.utcoffset()} in: {original!r}"
            )

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_valid_iso8601_utc(cls, value: str) -> str:
        """Validate that the timestamp is a well-formed ISO-8601 UTC string."""
        stripped = value.strip()
        normalised = cls._normalise_iso8601_string(stripped)
        parsed = cls._parse_to_datetime(normalised)
        cls._ensure_utc(parsed, stripped)
        return stripped

    @field_validator("event_type")
    @classmethod
    def event_type_must_not_be_blank(cls, value: str) -> str:
        """Reject event_type that is empty or whitespace-only."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("event_type must not be empty or whitespace-only")
        return stripped
