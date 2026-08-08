from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator


class Event(BaseModel):
    """Schema-validated event from the activity stream.

    All fields are required. ``event_timestamp`` must be a valid ISO-format
    timestamp. No field may be empty or consist only of whitespace.

    Use :meth:`from_dict` to safely construct an event from raw data — it
    returns ``None`` when validation fails instead of raising.
    """

    user_id: str
    product_id: str
    event_timestamp: str
    event_type: str

    @field_validator("user_id", "product_id", "event_timestamp", "event_type")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        """Reject strings that are empty or contain only whitespace."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty or whitespace-only")
        return stripped

    @field_validator("event_timestamp")
    @classmethod
    def _validate_iso_timestamp(cls, value: str) -> str:
        """Ensure the timestamp is a valid ISO-8601 datetime string."""
        # At this point the value has already been stripped by _require_non_blank.
        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise ValueError(
                f"event_timestamp must be a valid ISO-format timestamp, got: {value!r}"
            )
        return value

