from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from pipeline.event import Event

# =========================================================================
# Helpers
# =========================================================================

_VALID_KWARGS: dict[str, str] = {
    "user_id": "user-1",
    "product_id": "product-a",
    "event_timestamp": "2026-08-08T10:30:00",
    "event_type": "click",
}


def _make(**overrides: str) -> Event:
    kwargs = {**_VALID_KWARGS, **overrides}
    return Event(**kwargs)


# =========================================================================
# Positive cases
# =========================================================================

class TestValidConstruction:
    """Events that must be accepted."""

    def test_all_fields_present(self) -> None:
        event = _make()
        assert event.user_id == "user-1"
        assert event.product_id == "product-a"
        assert event.event_timestamp == "2026-08-08T10:30:00"
        assert event.event_type == "click"

    def test_whitespace_is_stripped(self) -> None:
        event = _make(
            user_id="  user-2  ",
            product_id="  product-b  ",
            event_timestamp="  2026-08-08T10:30:00  ",
            event_type="  view  ",
        )
        assert event.user_id == "user-2"
        assert event.product_id == "product-b"
        assert event.event_timestamp == "2026-08-08T10:30:00"
        assert event.event_type == "view"

    # -- ISO timestamp variants -------------------------------------------

    @pytest.mark.parametrize(
        "ts",
        [
            "2026-08-08",
            "2026-08-08T10:30:00",
            "2026-08-08T10:30:00.123456",
            "2026-08-08T10:30:00+00:00",
            "2026-08-08T10:30:00Z",
            "2026-08-08T10:30:00+11:00",
            "2026-08-08T10:30:00.123456+11:00",
        ],
    )
    def test_valid_iso_timestamp_formats(self, ts: str) -> None:
        event = _make(event_timestamp=ts)
        # Re-parse to confirm it is genuinely valid.
        parsed = datetime.fromisoformat(event.event_timestamp)
        assert isinstance(parsed, datetime)

    def test_date_only_is_accepted(self) -> None:
        """Spec says ISO format — dates without time are valid ISO."""
        event = _make(event_timestamp="2026-08-08")
        assert event.event_timestamp == "2026-08-08"


# =========================================================================
# Non-blank validation — one per field, plus whitespace-only variants
# =========================================================================

FIELDS = ["user_id", "product_id", "event_timestamp", "event_type"]


class TestNonBlankValidation:
    """Every field must reject empty and whitespace-only strings."""

    @pytest.mark.parametrize("field", FIELDS)
    def test_empty_string_is_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError) as exc:
            _make(**{field: ""})
        errors = exc.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == (field,)
        assert "empty or whitespace-only" in errors[0]["msg"]

    @pytest.mark.parametrize("field", FIELDS)
    def test_whitespace_only_is_rejected(self, field: str) -> None:
        for value in ("   ", "\t", "\n", "  \t\n  "):
            with pytest.raises(ValidationError) as exc:
                _make(**{field: value})
            assert "empty or whitespace-only" in str(exc.value)


# =========================================================================
# ISO timestamp validation
# =========================================================================

class TestTimestampValidation:
    """``event_timestamp`` must be a valid ISO-8601 string."""

    @pytest.mark.parametrize(
        "bad_ts",
        [
            "not-a-timestamp",
            "2026-08-08T10:30:00INVALID",
            "2026/08/08",
            "08-08-2026",
        ],
    )
    def test_invalid_iso_timestamp_is_rejected(self, bad_ts: str) -> None:
        with pytest.raises(ValidationError) as exc:
            _make(event_timestamp=bad_ts)
        errors = exc.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("event_timestamp",)
        assert "ISO-format" in errors[0]["msg"]

    def test_timestamp_still_checked_after_stripping(self) -> None:
        """Whitespace is stripped first, then format is validated."""
        with pytest.raises(ValidationError):
            _make(event_timestamp="   invalid   ")


# =========================================================================
# Missing fields
# =========================================================================

class TestMissingFields:
    """All four fields are required."""

    @pytest.mark.parametrize("field", FIELDS)
    def test_missing_field_is_rejected(self, field: str) -> None:
        kwargs = {**_VALID_KWARGS}
        del kwargs[field]
        with pytest.raises(ValidationError) as exc:
            Event(**kwargs)
        errors = exc.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == (field,)
        assert errors[0]["type"] == "missing"
