import pytest
from pydantic import ValidationError

from pipeline.event import Event


class TestEventPositive:
    """Happy-path scenarios for Event construction."""

    def test_valid_event_all_fields(self) -> None:
        """All required fields provided with valid values."""
        event = Event(
            user_id="user123",
            event_type="click",
            event_timestamp="2026-08-05T12:00:00",
        )
        assert event.user_id == "user123"
        assert event.event_type == "click"
        assert event.event_timestamp == "2026-08-05T12:00:00"

    def test_timestamp_with_z_suffix(self) -> None:
        """ISO 8601 timestamp with Z (UTC) suffix."""
        event = Event(
            user_id="u1",
            event_type="view",
            event_timestamp="2026-08-05T12:00:00Z",
        )
        assert event.event_timestamp == "2026-08-05T12:00:00Z"

    def test_timestamp_with_timezone_offset(self) -> None:
        """ISO 8601 timestamp with +HH:MM offset."""
        event = Event(
            user_id="u1",
            event_type="view",
            event_timestamp="2026-08-05T12:00:00+11:00",
        )
        assert event.event_timestamp == "2026-08-05T12:00:00+11:00"

    def test_timestamp_date_only(self) -> None:
        """ISO 8601 date-only format (no time component)."""
        event = Event(
            user_id="u1",
            event_type="view",
            event_timestamp="2026-08-05",
        )
        assert event.event_timestamp == "2026-08-05"

    def test_user_id_min_length_one(self) -> None:
        """Single-character user_id is valid."""
        event = Event(
            user_id="a",
            event_type="click",
            event_timestamp="2026-08-05T00:00:00",
        )
        assert event.user_id == "a"


class TestEventNegativeUserId:
    """Negative scenarios for the user_id field."""

    def test_user_id_empty_string(self) -> None:
        """Empty user_id should fail min_length=1 validation."""
        with pytest.raises(ValidationError) as exc_info:
            Event(
                user_id="",
                event_type="click",
                event_timestamp="2026-08-05T12:00:00",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("user_id",) for e in errors)

    def test_user_id_missing(self) -> None:
        """Missing user_id should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            Event(
                event_type="click",
                event_timestamp="2026-08-05T12:00:00",
            )  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("user_id",) for e in errors)


class TestEventNegativeEventType:
    """Negative scenarios for the event_type field."""

    def test_event_type_empty_string(self) -> None:
        """Empty event_type should fail min_length=1 validation."""
        with pytest.raises(ValidationError) as exc_info:
            Event(
                user_id="user123",
                event_type="",
                event_timestamp="2026-08-05T12:00:00",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_type",) for e in errors)

    def test_event_type_missing(self) -> None:
        """Missing event_type should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            Event(
                user_id="user123",
                event_timestamp="2026-08-05T12:00:00",
            )  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_type",) for e in errors)


class TestEventNegativeTimestamp:
    """Negative scenarios for the event_timestamp field."""

    def test_timestamp_empty_string(self) -> None:
        """Empty timestamp should fail min_length=1 validation."""
        with pytest.raises(ValidationError) as exc_info:
            Event(
                user_id="user123",
                event_type="click",
                event_timestamp="",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_timestamp",) for e in errors)

    def test_timestamp_missing(self) -> None:
        """Missing event_timestamp should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            Event(
                user_id="user123",
                event_type="click",
            )  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_timestamp",) for e in errors)

    def test_timestamp_not_iso_format(self) -> None:
        """A non-ISO string should fail the timestamp validator."""
        with pytest.raises(ValueError) as exc_info:
            Event(
                user_id="user123",
                event_type="click",
                event_timestamp="not-a-timestamp",
            )
        assert "ISO 8601" in str(exc_info.value)

    def test_timestamp_random_string(self) -> None:
        """A random word should fail the timestamp validator."""
        with pytest.raises(ValueError) as exc_info:
            Event(
                user_id="user123",
                event_type="click",
                event_timestamp="hello",
            )
        assert "ISO 8601" in str(exc_info.value)

    def test_timestamp_wrong_date_format(self) -> None:
        """A non-ISO date format (e.g. US-style) should fail."""
        with pytest.raises(ValueError) as exc_info:
            Event(
                user_id="user123",
                event_type="click",
                event_timestamp="08/05/2026",
            )
        assert "ISO 8601" in str(exc_info.value)


class TestEventNegativeInputType:
    """Negative scenarios for the top-level input type."""

    def test_input_not_a_dict_list(self) -> None:
        """Passing a list instead of a dict should raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            Event.model_validate(["user123", "click", "2026-08-05T12:00:00"])
        assert "dictionary" in str(exc_info.value)

    def test_input_not_a_dict_string(self) -> None:
        """Passing a string instead of a dict should raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            Event.model_validate("not a dict")
        assert "dictionary" in str(exc_info.value)

    def test_input_not_a_dict_none(self) -> None:
        """Passing None instead of a dict should raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            Event.model_validate(None)
        assert "dictionary" in str(exc_info.value)

    def test_input_empty_dict(self) -> None:
        """An empty dict should raise ValidationError (all fields missing)."""
        with pytest.raises(ValidationError) as exc_info:
            Event.model_validate({})
        errors = exc_info.value.errors()
        assert len(errors) == 3
        field_names = {e["loc"][0] for e in errors}
        assert field_names == {"user_id", "event_type", "event_timestamp"}


class TestEventEdgeCases:
    """Edge-case scenarios for Event construction."""

    def test_extra_fields_ignored(self) -> None:
        """Unknown fields should be ignored (pydantic default)."""
        event = Event(
            user_id="user123",
            event_type="click",
            event_timestamp="2026-08-05T12:00:00",
            extra_field="should be ignored",  # type: ignore[call-arg]
        )
        assert event.user_id == "user123"

    def test_model_dump_output(self) -> None:
        """model_dump() should return a plain dict of the event."""
        event = Event(
            user_id="user123",
            event_type="click",
            event_timestamp="2026-08-05T12:00:00",
        )
        dumped = event.model_dump()
        assert dumped == {
            "user_id": "user123",
            "event_type": "click",
            "event_timestamp": "2026-08-05T12:00:00",
        }
