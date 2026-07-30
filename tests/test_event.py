from datetime import datetime

import pytest
from pydantic import ValidationError

from src.experiment.event import Event


# -- positive cases ----------------------------------------------------------

VALID_EVENT = {
    "user_id": "user_1",
    "experiment_id": "exp_1",
    "variant_id": "variant_a",
    "timestamp": "2025-01-15T10:30:00",
    "event_type": "exposure",
}


def test_valid_event_constructs():
    """All fields provided and valid → Event is created."""
    ev = Event(**VALID_EVENT)
    assert ev.user_id == "user_1"
    assert ev.experiment_id == "exp_1"
    assert ev.variant_id == "variant_a"
    assert ev.timestamp == "2025-01-15T10:30:00"
    assert ev.event_type == "exposure"


def test_string_fields_strip_whitespace():
    """Leading and trailing whitespace is removed from string fields."""
    ev = Event(
        user_id="  user_2  ",
        experiment_id="  exp_2  ",
        variant_id="  variant_b  ",
        timestamp="2025-06-01T00:00:00",
        event_type="  exposure  ",
    )
    assert ev.user_id == "user_2"
    assert ev.experiment_id == "exp_2"
    assert ev.variant_id == "variant_b"
    assert ev.event_type == "exposure"


@pytest.mark.parametrize(
    "ts_input, expected_dt",
    [
        ("2025-01-15T10:30:00", datetime(2025, 1, 15, 10, 30, 0)),
        (
            "2025-01-15T10:30:00.123456",
            datetime(2025, 1, 15, 10, 30, 0, 123456),
        ),
    ],
)
def test_parsed_timestamp(ts_input, expected_dt):
    """parsed_timestamp returns the correct datetime for valid formats."""
    data = {**VALID_EVENT, "timestamp": ts_input}
    ev = Event(**data)
    assert ev.parsed_timestamp == expected_dt


# -- negative cases ----------------------------------------------------------


def test_empty_user_id_raises():
    """Empty user_id after stripping raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "user_id": ""})


def test_whitespace_only_user_id_raises():
    """Whitespace-only user_id raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "user_id": "   "})


def test_empty_experiment_id_raises():
    """Empty experiment_id after stripping raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "experiment_id": ""})


def test_empty_variant_id_raises():
    """Empty variant_id after stripping raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "variant_id": ""})


def test_empty_event_type_raises():
    """Empty event_type after stripping raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "event_type": ""})


def test_empty_timestamp_raises():
    """Empty timestamp raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "timestamp": ""})


def test_invalid_timestamp_format_raises():
    """A non-ISO-8601 timestamp raises a ValidationError."""
    with pytest.raises(ValidationError):
        Event(**{**VALID_EVENT, "timestamp": "15-01-2025"})


def test_missing_user_id_raises():
    """Missing a required field raises a ValidationError."""
    data = {k: v for k, v in VALID_EVENT.items() if k != "user_id"}
    with pytest.raises(ValidationError):
        Event(**data)
