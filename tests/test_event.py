from datetime import datetime

import pytest
from pydantic import ValidationError

from src.pipeline.event import Event


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------

def test_valid_event_all_fields() -> None:
    """All three fields present and valid."""
    event = Event(
        user_id="u1",
        datetime="2026-08-04T14:30:00",
        activity_type="login",
    )
    assert event.user_id == "u1"
    assert event.datetime == "2026-08-04T14:30:00"
    assert event.activity_type == "login"


def test_user_id_with_whitespace_is_allowed() -> None:
    """Leading / trailing spaces are kept — only *blank* ids are rejected."""
    event = Event(user_id="  u1  ", datetime="2026-08-04T00:00:00", activity_type="x")
    assert event.user_id == "  u1  "


def test_datetime_with_timezone() -> None:
    """ISO-8601 with a timezone offset should be valid."""
    event = Event(
        user_id="u1",
        datetime="2026-08-04T14:30:00+10:00",
        activity_type="login",
    )
    assert event.timestamp == datetime.fromisoformat("2026-08-04T14:30:00+10:00")


def test_timestamp_property() -> None:
    """``timestamp`` returns the parsed datetime object."""
    event = Event(user_id="u1", datetime="2026-08-04T09:15:00", activity_type="click")
    assert event.timestamp == datetime(2026, 8, 4, 9, 15, 0)


# ---------------------------------------------------------------------------
# Negative cases — missing fields
# ---------------------------------------------------------------------------

def test_missing_user_id_raises() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Event(datetime="2026-08-04T00:00:00", activity_type="x")  # type: ignore[arg-type]


def test_missing_datetime_raises() -> None:
    with pytest.raises(ValidationError, match="datetime"):
        Event(user_id="u1", activity_type="x")  # type: ignore[arg-type]


def test_missing_activity_type_raises() -> None:
    with pytest.raises(ValidationError, match="activity_type"):
        Event(user_id="u1", datetime="2026-08-04T00:00:00")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Negative cases — invalid values
# ---------------------------------------------------------------------------

def test_user_id_empty_raises() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Event(user_id="", datetime="2026-08-04T00:00:00", activity_type="x")


def test_user_id_only_spaces_raises() -> None:
    with pytest.raises(ValidationError, match="user_id"):
        Event(user_id="   ", datetime="2026-08-04T00:00:00", activity_type="x")


def test_datetime_unparseable_raises() -> None:
    with pytest.raises(ValidationError, match="datetime"):
        Event(user_id="u1", datetime="not-a-date", activity_type="x")


def test_datetime_invalid_date_raises() -> None:
    """Feb 30 does not exist — should fail parsing."""
    with pytest.raises(ValidationError, match="datetime"):
        Event(user_id="u1", datetime="2026-02-30T12:00:00", activity_type="x")


# ---------------------------------------------------------------------------
# Negative cases — wrong types
# ---------------------------------------------------------------------------

def test_user_id_wrong_type_raises() -> None:
    with pytest.raises(ValidationError):
        Event(user_id=123, datetime="2026-08-04T00:00:00", activity_type="x")  # type: ignore[arg-type]


def test_datetime_wrong_type_raises() -> None:
    with pytest.raises(ValidationError):
        Event(user_id="u1", datetime=12345, activity_type="x")  # type: ignore[arg-type]


def test_activity_type_wrong_type_raises() -> None:
    with pytest.raises(ValidationError):
        Event(user_id="u1", datetime="2026-08-04T00:00:00", activity_type=None)  # type: ignore[arg-type]
