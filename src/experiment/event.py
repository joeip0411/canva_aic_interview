from datetime import datetime

from pydantic import BaseModel, field_validator

# ISO-8601 formats accepted for timestamp validation and parsing.
_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
)


class Event(BaseModel):
    """A single exposure event from the raw experiment stream.

    Represents one recorded instance of a user being exposed to a specific
    variant within an experiment at a point in time.
    """

    user_id: str
    experiment_id: str
    variant_id: str
    timestamp: str
    event_type: str

    @field_validator("user_id", "experiment_id", "variant_id", "event_type")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        """Ensure string fields are non-empty after stripping whitespace."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("string field must not be empty")
        return stripped

    @property
    def parsed_timestamp(self) -> datetime:
        """Return the validated ``timestamp`` string as a ``datetime``."""
        for fmt in _TS_FORMATS:
            try:
                return datetime.strptime(self.timestamp, fmt)
            except ValueError:
                continue
        # Should never be reached — the validator guarantees a match.
        raise ValueError(  # pragma: no cover
            f"timestamp is not a recognised ISO-8601 format: "
            f"{self.timestamp!r}"
        )

    @field_validator("timestamp")
    @classmethod
    def _validate_iso_timestamp(cls, value: str) -> str:
        """Ensure the timestamp is a valid ISO-8601 datetime string."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("timestamp must not be empty")
        for fmt in _TS_FORMATS:
            try:
                datetime.strptime(stripped, fmt)
                return stripped
            except ValueError:
                continue
        raise ValueError(
            f"timestamp must be a valid ISO-8601 string, got: {stripped!r}"
        )
