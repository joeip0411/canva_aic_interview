from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Event(BaseModel):
    """A validated input event from a user interacting with the application.

    Performs schema validation on the raw input dictionary before
    the event enters the processing pipeline.
    """

    user_id: str = Field(..., min_length=1, description="Identifier of the user who triggered the event")
    event_type: str = Field(..., min_length=1, description="Category of the interaction (e.g. click, view)")
    event_timestamp: str = Field(
        ...,
        min_length=1,
        description="ISO 8601 timestamp of when the event occurred",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_input_is_a_dict(cls, data: Any) -> Any:
        """Ensure the raw input is a dictionary before field-level validation runs."""
        if not isinstance(data, dict):
            raise TypeError(f"Event input must be a dictionary, got {type(data).__name__}")
        return data

    @model_validator(mode="after")
    def validate_timestamp_is_iso(self) -> "Event":
        """Validate that event_timestamp is a well-formed ISO 8601 datetime string."""
        try:
            # Parse as ISO 8601 — accepts both 'Z' suffix and '+00:00' offsets
            datetime.fromisoformat(self.event_timestamp)
        except ValueError as exc:
            raise ValueError(
                f"event_timestamp must be a valid ISO 8601 datetime string, "
                f"got '{self.event_timestamp}'"
            ) from exc
        return self
