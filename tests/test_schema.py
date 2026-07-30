"""Unit tests for the Event Pydantic model."""

import pytest
from pydantic import ValidationError

from src.pipeline.schema import Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_KWARGS = {
    "asset_id": "asset_001",
    "event_time": "2026-07-15T10:30:00",
    "user_id": "user_42",
    "creator_id": "creator_7",
    "event_type": "use",
}


def _assert_missing(field: str) -> None:
    """Verify that omitting *field* raises ValidationError."""
    kwargs = {**_VALID_KWARGS}
    del kwargs[field]
    with pytest.raises(ValidationError):
        Event.model_validate(kwargs)


def _assert_empty(field: str) -> None:
    """Verify that *field* set to ``""`` raises ValidationError."""
    with pytest.raises(ValidationError):
        Event.model_validate({**_VALID_KWARGS, field: ""})


def _assert_none(field: str) -> None:
    """Verify that *field* set to ``None`` raises ValidationError."""
    with pytest.raises(ValidationError):
        Event.model_validate({**_VALID_KWARGS, field: None})


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------

class TestEventValid:
    """Valid events that must pass validation."""

    def test_all_fields_present_and_valid(self) -> None:
        """Happy path — every field has a valid value."""
        event = Event.model_validate(_VALID_KWARGS)
        assert event.asset_id == "asset_001"
        assert event.event_time == "2026-07-15T10:30:00"
        assert event.user_id == "user_42"
        assert event.creator_id == "creator_7"
        assert event.event_type == "use"

    @pytest.mark.parametrize("time_str", [
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:00Z",
        "2026-12-31T23:59:59.999999",
    ])
    def test_various_iso8601_formats(self, time_str: str) -> None:
        """Valid ISO‑8601 variants should all be accepted."""
        event = Event.model_validate({**_VALID_KWARGS, "event_time": time_str})
        assert event.event_time == time_str

    def test_minimum_length_strings(self) -> None:
        """Single‑character non‑empty strings are valid."""
        event = Event.model_validate({
            "asset_id": "a",
            "event_time": "2026-07-15T10:30:00",
            "user_id": "u",
            "creator_id": "c",
            "event_type": "x",
        })
        assert event is not None


# ---------------------------------------------------------------------------
# Negative cases — asset_id
# ---------------------------------------------------------------------------

class TestEventAssetId:
    """Rejections specific to ``asset_id``."""

    def test_missing_raises(self) -> None:
        _assert_missing("asset_id")

    def test_empty_raises(self) -> None:
        _assert_empty("asset_id")

    def test_none_raises(self) -> None:
        _assert_none("asset_id")


# ---------------------------------------------------------------------------
# Negative cases — event_time
# ---------------------------------------------------------------------------

class TestEventEventTime:
    """Rejections specific to ``event_time``."""

    def test_missing_raises(self) -> None:
        _assert_missing("event_time")

    def test_empty_raises(self) -> None:
        _assert_empty("event_time")

    def test_none_raises(self) -> None:
        _assert_none("event_time")

    @pytest.mark.parametrize("bad_value", [
        "not-a-date",
        "2026-13-01",           # month 13
        "2026-02-30",           # Feb 30
        "2026-01-01T25:00:00",  # hour 25
        "yesterday",
        "",
    ])
    def test_invalid_datetime_raises(self, bad_value: str) -> None:
        with pytest.raises(ValidationError):
            Event.model_validate({**_VALID_KWARGS, "event_time": bad_value})


# ---------------------------------------------------------------------------
# Negative cases — user_id
# ---------------------------------------------------------------------------

class TestEventUserId:
    """Rejections specific to ``user_id``."""

    def test_missing_raises(self) -> None:
        _assert_missing("user_id")

    def test_empty_raises(self) -> None:
        _assert_empty("user_id")

    def test_none_raises(self) -> None:
        _assert_none("user_id")


# ---------------------------------------------------------------------------
# Negative cases — creator_id
# ---------------------------------------------------------------------------

class TestEventCreatorId:
    """Rejections specific to ``creator_id``."""

    def test_missing_raises(self) -> None:
        _assert_missing("creator_id")

    def test_empty_raises(self) -> None:
        _assert_empty("creator_id")

    def test_none_raises(self) -> None:
        _assert_none("creator_id")


# ---------------------------------------------------------------------------
# Negative cases — event_type
# ---------------------------------------------------------------------------

class TestEventEventType:
    """Rejections specific to ``event_type``."""

    def test_missing_raises(self) -> None:
        _assert_missing("event_type")

    def test_empty_raises(self) -> None:
        _assert_empty("event_type")

    def test_none_raises(self) -> None:
        _assert_none("event_type")
