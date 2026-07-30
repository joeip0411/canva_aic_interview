"""Pydantic models for input event validation."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class Event(BaseModel):
    """A raw marketplace interaction event.

    Validates that all required fields are present, non-empty, and that
    ``event_time`` is a valid ISO‑8601 datetime string before the event
    enters the stream processor.
    """

    asset_id: Annotated[str, Field(min_length=1, description="Unique identifier for the marketplace asset.")]
    event_time: Annotated[str, Field(min_length=1, description="ISO-8601 UTC timestamp of the interaction.")]
    user_id: Annotated[str, Field(min_length=1, description="Unique identifier for the interacting user.")]
    creator_id: Annotated[str, Field(min_length=1, description="Unique identifier for the asset's creator.")]
    event_type: Annotated[str, Field(min_length=1, description="Type of interaction (e.g., view, use, remix).")]

    @field_validator("event_time")
    @classmethod
    def _must_be_iso8601(cls, v: str) -> str:
        """Validate that *event_time* is a valid ISO‑8601 datetime string."""
        try:
            datetime.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError(f"'{v}' is not a valid ISO‑8601 datetime string.")
        return v
