from datetime import datetime as dt

from pydantic import BaseModel, field_validator


class Event(BaseModel):
    """A validated user-activity event.

    Fields match the input schema defined in specification.md. Pydantic
    enforces types and rejects missing fields at construction time.
    """

    user_id: str
    datetime: str
    activity_type: str

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id must not be blank or contain only whitespace")
        return v

    @field_validator("datetime")
    @classmethod
    def datetime_must_be_parsable(cls, v: str) -> str:
        try:
            dt.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError(
                f"datetime must be a valid ISO-8601 string, got: {v!r}"
            )
        return v

    @property
    def timestamp(self) -> dt:
        """The ``datetime`` field parsed into a :class:`datetime` object."""
        return dt.fromisoformat(self.datetime)
