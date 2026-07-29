import pytest
from pydantic import ValidationError

from datetime import datetime, timedelta, timezone

from src.pipeline.pipeline import OutputSummaryData, RawEventData, StreamProcessor


# ------------------------------------------------------------------
# Helper — generate a non-stale ISO-8601 timestamp relative to now.
# ------------------------------------------------------------------


def _ts(minutes_ago: int = 5) -> str:
    """Return an ISO-8601 UTC timestamp *minutes_ago* minutes before now."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# ==================================================================
# Positive cases — valid input should construct without error.
# ==================================================================


def test_valid_event_with_all_fields() -> None:
    """A complete, well-formed event should parse successfully."""
    event = RawEventData(
        user_id="user_123",
        timestamp="2026-03-01T10:00:00Z",
        event_type="create_design",
        meta={"platform": "web"},
    )
    assert event.user_id == "user_123"
    assert event.timestamp == "2026-03-01T10:00:00Z"
    assert event.event_type == "create_design"
    assert event.meta == {"platform": "web"}


def test_valid_event_with_empty_meta() -> None:
    """meta defaults to an empty dict when omitted."""
    event = RawEventData(
        user_id="user_456",
        timestamp="2026-07-01T12:00:00Z",
        event_type="edit_design",
    )
    assert event.meta == {}


def test_valid_event_with_complex_meta() -> None:
    """meta can hold arbitrary key-value pairs."""
    event = RawEventData(
        user_id="user_789",
        timestamp="2026-03-15T08:30:00+00:00",
        event_type="export_design",
        meta={"platform": "mobile", "version": 2, "tags": ["beta", "preview"]},
    )
    assert event.meta["platform"] == "mobile"
    assert event.meta["version"] == 2
    assert event.meta["tags"] == ["beta", "preview"]


def test_timestamp_with_explicit_utc_offset() -> None:
    """'+00:00' should be accepted just like 'Z'."""
    event = RawEventData(
        user_id="user_001",
        timestamp="2026-01-01T00:00:00+00:00",
        event_type="login",
    )
    assert event.timestamp == "2026-01-01T00:00:00+00:00"


# ------------------------------------------------------------------
# Whitespace trimming
# ------------------------------------------------------------------


def test_user_id_strips_whitespace() -> None:
    """Leading and trailing whitespace on user_id is stripped."""
    event = RawEventData(
        user_id="  user_abc  ",
        timestamp="2026-03-01T10:00:00Z",
        event_type="create_design",
    )
    assert event.user_id == "user_abc"


def test_event_type_strips_whitespace() -> None:
    """Leading and trailing whitespace on event_type is stripped."""
    event = RawEventData(
        user_id="user_abc",
        timestamp="2026-03-01T10:00:00Z",
        event_type="  create_design  ",
    )
    assert event.event_type == "create_design"


# ==================================================================
# Negative cases — invalid input should raise ValidationError.
# ==================================================================


# ------------------------------------------------------------------
# user_id validation
# ------------------------------------------------------------------


def test_missing_user_id_raises() -> None:
    """Omitting user_id must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            timestamp="2026-03-01T10:00:00Z",
            event_type="create_design",
        )


def test_empty_user_id_raises() -> None:
    """An empty user_id string must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="",
            timestamp="2026-03-01T10:00:00Z",
            event_type="create_design",
        )


def test_whitespace_only_user_id_raises() -> None:
    """A user_id containing only whitespace must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="   ",
            timestamp="2026-03-01T10:00:00Z",
            event_type="create_design",
        )


# ------------------------------------------------------------------
# timestamp validation
# ------------------------------------------------------------------


def test_missing_timestamp_raises() -> None:
    """Omitting timestamp must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            event_type="create_design",
        )


def test_empty_timestamp_raises() -> None:
    """An empty timestamp string must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="",
            event_type="create_design",
        )


def test_timestamp_not_iso8601_raises() -> None:
    """A non-ISO-8601 string (e.g. 'yesterday') must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="yesterday at noon",
            event_type="create_design",
        )


def test_timestamp_without_timezone_raises() -> None:
    """An ISO-8601 string without a timezone offset must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="2026-03-01T10:00:00",
            event_type="create_design",
        )


def test_timestamp_with_non_utc_offset_raises() -> None:
    """A timestamp with a non-UTC offset (e.g. +05:30) must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="2026-03-01T10:00:00+05:30",
            event_type="create_design",
        )


def test_timestamp_with_negative_non_utc_offset_raises() -> None:
    """A timestamp with a negative non-UTC offset (e.g. -08:00) must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="2026-03-01T10:00:00-08:00",
            event_type="create_design",
        )


# ------------------------------------------------------------------
# event_type validation
# ------------------------------------------------------------------


def test_missing_event_type_raises() -> None:
    """Omitting event_type must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="2026-03-01T10:00:00Z",
        )


def test_empty_event_type_raises() -> None:
    """An empty event_type string must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="2026-03-01T10:00:00Z",
            event_type="",
        )


def test_whitespace_only_event_type_raises() -> None:
    """An event_type containing only whitespace must fail."""
    with pytest.raises(ValidationError):
        RawEventData(
            user_id="user_123",
            timestamp="2026-03-01T10:00:00Z",
            event_type="   ",
        )


# ==================================================================
# OutputSummaryData — positive cases
# ==================================================================


def test_valid_summary_with_all_fields() -> None:
    """A complete session summary should construct and retain all values."""
    summary = OutputSummaryData(
        session_id="user_1232026-03-01T10:00:00Z2026-03-01T10:05:00Z",
        user_id="user_123",
        session_start="2026-03-01T10:00:00Z",
        session_end="2026-03-01T10:05:00Z",
        total_events=3,
        is_ai_enhanced=True,
    )
    assert summary.session_id == "user_1232026-03-01T10:00:00Z2026-03-01T10:05:00Z"
    assert summary.user_id == "user_123"
    assert summary.session_start == "2026-03-01T10:00:00Z"
    assert summary.session_end == "2026-03-01T10:05:00Z"
    assert summary.total_events == 3
    assert summary.is_ai_enhanced is True


def test_summary_with_minimal_events() -> None:
    """A single-event session (total_events=1) is valid."""
    summary = OutputSummaryData(
        session_id="u12026-01-01T00:00:00Z2026-01-01T00:00:00Z",
        user_id="u1",
        session_start="2026-01-01T00:00:00Z",
        session_end="2026-01-01T00:00:00Z",
        total_events=1,
        is_ai_enhanced=False,
    )
    assert summary.total_events == 1
    assert summary.is_ai_enhanced is False


def test_summary_not_ai_enhanced() -> None:
    """is_ai_enhanced=False should be preserved."""
    summary = OutputSummaryData(
        session_id="user_x2026-02-01T00:00:00Z2026-02-01T00:01:00Z",
        user_id="user_x",
        session_start="2026-02-01T00:00:00Z",
        session_end="2026-02-01T00:01:00Z",
        total_events=5,
        is_ai_enhanced=False,
    )
    assert summary.is_ai_enhanced is False


def test_summary_timestamps_with_explicit_utc_offset() -> None:
    """'+00:00' offset should be accepted for session_start and session_end."""
    summary = OutputSummaryData(
        session_id="abc2026-06-01T00:00:00+00:002026-06-01T01:00:00+00:00",
        user_id="abc",
        session_start="2026-06-01T00:00:00+00:00",
        session_end="2026-06-01T01:00:00+00:00",
        total_events=2,
        is_ai_enhanced=True,
    )
    assert summary.session_start == "2026-06-01T00:00:00+00:00"


# ------------------------------------------------------------------
# Whitespace trimming
# ------------------------------------------------------------------


def test_summary_user_id_strips_whitespace() -> None:
    """Leading/trailing whitespace on user_id is stripped."""
    summary = OutputSummaryData(
        session_id="x2026-01-01T00:00:00Z2026-01-01T00:00:00Z",
        user_id="  user_abc  ",
        session_start="2026-01-01T00:00:00Z",
        session_end="2026-01-01T00:00:00Z",
        total_events=1,
        is_ai_enhanced=False,
    )
    assert summary.user_id == "user_abc"


# ==================================================================
# OutputSummaryData — negative cases
# ==================================================================


# ------------------------------------------------------------------
# session_id validation
# ------------------------------------------------------------------


def test_summary_missing_session_id_raises() -> None:
    """Omitting session_id must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_empty_session_id_raises() -> None:
    """An empty session_id must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


# ------------------------------------------------------------------
# user_id validation
# ------------------------------------------------------------------


def test_summary_missing_user_id_raises() -> None:
    """Omitting user_id must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_empty_user_id_raises() -> None:
    """An empty user_id must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_whitespace_only_user_id_raises() -> None:
    """A whitespace-only user_id must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="   ",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


# ------------------------------------------------------------------
# session_start validation
# ------------------------------------------------------------------


def test_summary_missing_session_start_raises() -> None:
    """Omitting session_start must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_empty_session_start_raises() -> None:
    """An empty session_start must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_session_start_not_iso8601_raises() -> None:
    """A non-ISO-8601 session_start must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="last Tuesday",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_session_start_without_timezone_raises() -> None:
    """A session_start without a timezone offset must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_session_start_non_utc_raises() -> None:
    """A session_start with a non-UTC offset must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00+05:30",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


# ------------------------------------------------------------------
# session_end validation
# ------------------------------------------------------------------


def test_summary_missing_session_end_raises() -> None:
    """Omitting session_end must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_empty_session_end_raises() -> None:
    """An empty session_end must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_session_end_not_iso8601_raises() -> None:
    """A non-ISO-8601 session_end must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="later that day",
            total_events=3,
            is_ai_enhanced=False,
        )


def test_summary_session_end_non_utc_raises() -> None:
    """A session_end with a non-UTC offset must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00-08:00",
            total_events=3,
            is_ai_enhanced=False,
        )


# ------------------------------------------------------------------
# total_events validation
# ------------------------------------------------------------------


def test_summary_missing_total_events_raises() -> None:
    """Omitting total_events must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            is_ai_enhanced=False,
        )


def test_summary_zero_total_events_raises() -> None:
    """total_events=0 must fail (gt=0 constraint)."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=0,
            is_ai_enhanced=False,
        )


def test_summary_negative_total_events_raises() -> None:
    """A negative total_events must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=-1,
            is_ai_enhanced=False,
        )


# ------------------------------------------------------------------
# is_ai_enhanced validation
# ------------------------------------------------------------------


def test_summary_missing_is_ai_enhanced_raises() -> None:
    """Omitting is_ai_enhanced must fail."""
    with pytest.raises(ValidationError):
        OutputSummaryData(
            session_id="abc",
            user_id="user_123",
            session_start="2026-03-01T10:00:00Z",
            session_end="2026-03-01T10:05:00Z",
            total_events=3,
        )


# ==================================================================
# StreamProcessor — integration tests
# ==================================================================


# ------------------------------------------------------------------
# Scenario 1 — user with multiple events, AI-enhanced = true
# ------------------------------------------------------------------


def test_stream_single_user_ai_enhanced() -> None:
    """Three events within 30 min, one of them 'use_ai_magic'."""
    events: list[dict[str, object]] = [
        {"user_id": "u1", "timestamp": _ts(25), "event_type": "open_design"},
        {"user_id": "u1", "timestamp": _ts(20), "event_type": "use_ai_magic"},
        {"user_id": "u1", "timestamp": _ts(15), "event_type": "save_design"},
    ]
    processor = StreamProcessor()
    results = list(processor.process(events))

    assert len(results) == 1
    summary = results[0]
    assert summary.user_id == "u1"
    assert summary.total_events == 3
    assert summary.is_ai_enhanced is True
    # session_id is user_id + session_start + session_end
    assert summary.session_id.startswith("u1")


# ------------------------------------------------------------------
# Scenario 2 — user with multiple events, AI-enhanced = false
# ------------------------------------------------------------------


def test_stream_single_user_not_ai_enhanced() -> None:
    """Four events within 30 min, none of them 'use_ai_magic'."""
    events: list[dict[str, object]] = [
        {"user_id": "u2", "timestamp": _ts(28), "event_type": "open_design"},
        {"user_id": "u2", "timestamp": _ts(20), "event_type": "edit_text"},
        {"user_id": "u2", "timestamp": _ts(12), "event_type": "add_image"},
        {"user_id": "u2", "timestamp": _ts(5), "event_type": "export_design"},
    ]
    processor = StreamProcessor()
    results = list(processor.process(events))

    assert len(results) == 1
    summary = results[0]
    assert summary.user_id == "u2"
    assert summary.total_events == 4
    assert summary.is_ai_enhanced is False


# ------------------------------------------------------------------
# Scenario 3 — some events are invalid, valid ones still produce
#              correct session summary.
# ------------------------------------------------------------------


def test_stream_some_invalid_events() -> None:
    """Invalid events are skipped; only valid ones contribute to the session."""
    events: list[dict[str, object]] = [
        {"user_id": "u3", "timestamp": _ts(22), "event_type": "open_design"},
        # Invalid — empty user_id.
        {"user_id": "", "timestamp": _ts(19), "event_type": "bad_event"},
        {"user_id": "u3", "timestamp": _ts(16), "event_type": "edit_design"},
        # Invalid — missing user_id entirely.
        {"timestamp": _ts(13), "event_type": "orphan_event"},
        {"user_id": "u3", "timestamp": _ts(10), "event_type": "use_ai_magic"},
    ]
    processor = StreamProcessor()
    results = list(processor.process(events))

    assert len(results) == 1
    summary = results[0]
    assert summary.user_id == "u3"
    # Only 3 valid events contributed.
    assert summary.total_events == 3
    # The third valid event was 'use_ai_magic'.
    assert summary.is_ai_enhanced is True


# ------------------------------------------------------------------
# Scenario 4 — all events are invalid.
# ------------------------------------------------------------------


def test_stream_all_invalid_events() -> None:
    """When every event fails validation, no sessions are produced."""
    events: list[dict[str, object]] = [
        # Missing user_id.
        {"timestamp": _ts(10), "event_type": "e1"},
        # Empty user_id.
        {"user_id": "", "timestamp": _ts(8), "event_type": "e2"},
        # Non-ISO timestamp.
        {"user_id": "u4", "timestamp": "not-a-time", "event_type": "e3"},
    ]
    processor = StreamProcessor()
    results = list(processor.process(events))

    assert len(results) == 0


# ------------------------------------------------------------------
# Scenario 5 — stale events (> 30 min old) are dropped.
# ------------------------------------------------------------------


def test_stream_stale_events_dropped() -> None:
    """Events whose timestamps are > 30 min in the past are discarded.

    The remaining non-stale events form the session correctly.
    """
    events: list[dict[str, object]] = [
        {"user_id": "u5", "timestamp": _ts(25), "event_type": "open_design"},
        # This timestamp is 45 minutes ago — stale, should be dropped.
        {"user_id": "u5", "timestamp": _ts(45), "event_type": "stale_event"},
        {"user_id": "u5", "timestamp": _ts(10), "event_type": "save_design"},
        # This timestamp is 60 minutes ago — stale, should be dropped.
        {"user_id": "u5", "timestamp": _ts(60), "event_type": "another_stale"},
    ]
    processor = StreamProcessor()
    results = list(processor.process(events))

    assert len(results) == 1
    summary = results[0]
    assert summary.user_id == "u5"
    # Only the 2 non-stale events should be counted.
    assert summary.total_events == 2
    assert summary.is_ai_enhanced is False
