import logging

import pytest
from pydantic import ValidationError

from src.pipeline.pipeline import Aggregator, Event

# =============================================================================
# Helpers
# =============================================================================

VALID_EVENT_KWARGS: dict = {
    "user_id": "user-1",
    "workspace_id": "ws-abc",
    "action": "login",
    "event_timestamp": "2025-07-29T14:30:00Z",
    "metadata": {"browser": "chrome", "version": 120},
}

# =============================================================================
# Event — positive cases
# =============================================================================

class TestEventPositive:
    """Happy-path construction and attribute checks for Event."""

    def test_all_fields_stored_correctly(self) -> None:
        e = Event(**VALID_EVENT_KWARGS)
        assert e.user_id == "user-1"
        assert e.workspace_id == "ws-abc"
        assert e.action == "login"
        assert e.event_timestamp == "2025-07-29T14:30:00Z"
        assert e.metadata == {"browser": "chrome", "version": 120}

    def test_timestamp_with_Z_suffix(self) -> None:
        e = Event(**{**VALID_EVENT_KWARGS, "event_timestamp": "2025-01-01T00:00:00Z"})
        assert e.event_timestamp == "2025-01-01T00:00:00Z"

    def test_timestamp_with_utc_offset(self) -> None:
        e = Event(**{**VALID_EVENT_KWARGS, "event_timestamp": "2025-06-15T12:00:00+00:00"})
        assert e.event_timestamp == "2025-06-15T12:00:00+00:00"

    def test_metadata_empty_dict(self) -> None:
        e = Event(**{**VALID_EVENT_KWARGS, "metadata": {}})
        assert e.metadata == {}

    def test_metadata_nested_values(self) -> None:
        nested = {"tags": ["a", "b"], "info": {"nested": True}}
        e = Event(**{**VALID_EVENT_KWARGS, "metadata": nested})
        assert e.metadata == nested

    def test_user_id_arbitrary_string(self) -> None:
        e = Event(**{**VALID_EVENT_KWARGS, "user_id": "uid-12345-alpha"})
        assert e.user_id == "uid-12345-alpha"

    def test_workspace_id_arbitrary_string(self) -> None:
        e = Event(**{**VALID_EVENT_KWARGS, "workspace_id": "ws_team_42"})
        assert e.workspace_id == "ws_team_42"

    def test_model_dump_returns_all_fields(self) -> None:
        e = Event(**VALID_EVENT_KWARGS)
        data = e.model_dump()
        assert set(data.keys()) == {"user_id", "workspace_id", "action", "event_timestamp", "metadata"}


# =============================================================================
# Event — negative cases
# =============================================================================

class TestEventNegative:
    """Error cases for Event construction."""

    @pytest.mark.parametrize("missing_field", [
        "user_id",
        "workspace_id",
        "action",
        "event_timestamp",
        "metadata",
    ])
    def test_missing_required_field_raises(self, missing_field: str) -> None:
        kwargs = {**VALID_EVENT_KWARGS}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            Event(**kwargs)

    def test_user_id_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            Event(**{**VALID_EVENT_KWARGS, "user_id": 123})  # type: ignore[arg-type]

    def test_workspace_id_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            Event(**{**VALID_EVENT_KWARGS, "workspace_id": None})  # type: ignore[arg-type]

    def test_action_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            Event(**{**VALID_EVENT_KWARGS, "action": 42})  # type: ignore[arg-type]

    def test_event_timestamp_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            Event(**{**VALID_EVENT_KWARGS, "event_timestamp": 20250729})  # type: ignore[arg-type]

    def test_metadata_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            Event(**{**VALID_EVENT_KWARGS, "metadata": "not-a-dict"})  # type: ignore[arg-type]

    # -- Timestamp validation -------------------------------------------------

    def test_timestamp_naive_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(**{**VALID_EVENT_KWARGS, "event_timestamp": "2025-07-29T14:30:00"})
        assert "UTC-aware" in str(exc_info.value)

    def test_timestamp_non_utc_offset_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(**{**VALID_EVENT_KWARGS, "event_timestamp": "2025-07-29T14:30:00+05:00"})
        assert "UTC" in str(exc_info.value)

    def test_timestamp_garbage_string_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(**{**VALID_EVENT_KWARGS, "event_timestamp": "not-a-timestamp"})
        assert "Invalid ISO-8601" in str(exc_info.value)

    def test_timestamp_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(**{**VALID_EVENT_KWARGS, "event_timestamp": ""})
        assert "Invalid ISO-8601" in str(exc_info.value)


# =============================================================================
# Helpers for integration tests
# =============================================================================

def _event(
    user_id: str,
    workspace_id: str,
    action: str,
    event_timestamp: str,
    metadata: dict | None = None,
) -> Event:
    """Shorthand to build a valid Event with less boilerplate."""
    return Event(
        user_id=user_id,
        workspace_id=workspace_id,
        action=action,
        event_timestamp=event_timestamp,
        metadata=metadata if metadata is not None else {},
    )


# =============================================================================
# Aggregator — integration tests
# =============================================================================

class TestAggregatorHappyPath:
    """Single-workspace scenario: valid events, clean session termination."""

    def test_single_workspace_session_and_termination(self, caplog) -> None:  # type: ignore[no-untyped-def]
        caplog.set_level(logging.INFO)

        agg = Aggregator()

        # -- Batch 1: active session within a few days ---------------------------
        batch1 = [
            _event("u1", "ws-a", "login",                         "2025-01-01T10:00:00Z"),
            _event("u2", "ws-a", "edit",                          "2025-01-02T14:00:00Z"),
            _event("u1", "ws-a", "edit",                          "2025-01-02T16:00:00Z"),  # duplicate action — proves event counting
            _event("u1", "ws-a", "purchase_pro_subscription",     "2025-01-03T09:00:00Z"),
        ]
        summaries = list(agg.process(batch1))
        assert summaries == []  # session still active, no termination

        # -- Batch 2: event 32 days later triggers termination ------------------
        # gap from 2025-01-03 to 2025-02-04 = 32 days > 30
        batch2 = [
            _event("u1", "ws-a", "logout", "2025-02-04T12:00:00Z"),
        ]
        summaries = list(agg.process(batch2))

        assert len(summaries) == 1
        s = summaries[0]
        assert s["workspace_id"] == "ws-a"
        assert s["user_count"] == 2         # u1, u2 (distinct)
        assert s["action_count"] == 4       # 4 events: login, edit, edit, purchase_pro_subscription
        assert s["pro_subscription_count"] == 1

        # -- Batch 3: post-termination event for same workspace → ignored --------
        batch3 = [
            _event("u2", "ws-a", "comment", "2025-02-05T08:00:00Z"),
        ]
        summaries = list(agg.process(batch3))
        assert summaries == []  # no new summary emitted

        # Verify the WARNING was logged
        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("already-terminated" in w for w in warnings)
        assert any("ws-a" in w for w in warnings)


class TestAggregatorMixedValidInvalid:
    """Two interleaved workspaces with termination, invalid post-termination
    events, and out-of-order delivery."""

    def test_mixed_scenario_yields_correct_summaries(self, caplog) -> None:  # type: ignore[no-untyped-def]
        caplog.set_level(logging.INFO)

        agg = Aggregator()

        # -- Batch 1: interleaved events for ws-c and ws-d ----------------------
        batch1 = [
            _event("u1", "ws-c", "login",                        "2025-06-01T10:00:00Z"),
            _event("u3", "ws-d", "login",                        "2025-06-01T11:00:00Z"),
            _event("u2", "ws-c", "edit",                         "2025-06-03T09:00:00Z"),
            _event("u3", "ws-d", "purchase_pro_subscription",    "2025-06-03T10:00:00Z"),
            _event("u1", "ws-c", "edit",                         "2025-06-04T10:00:00Z"),  # duplicate action — proves per-event counting
            _event("u1", "ws-c", "purchase_pro_subscription",    "2025-06-05T14:00:00Z"),
        ]
        summaries = list(agg.process(batch1))
        assert summaries == []  # both still active

        # -- Batch 2: ws-c terminates (gap > 30 days) ---------------------------
        # latest_ts for ws-c = 2025-06-05; new event = 2025-07-10
        # gap = 35 days > 30 → terminate, this event NOT counted
        batch2 = [
            _event("u1", "ws-c", "logout", "2025-07-10T08:00:00Z"),
        ]
        summaries = list(agg.process(batch2))
        assert len(summaries) == 1

        s_c = summaries[0]
        assert s_c["workspace_id"] == "ws-c"
        assert s_c["user_count"] == 2        # u1, u2 (distinct)
        assert s_c["action_count"] == 4      # 4 events total (login, edit×2, purchase) — not unique actions
        assert s_c["pro_subscription_count"] == 1

        # -- Batch 3: invalid — events for terminated ws-c are ignored ----------
        batch3 = [
            _event("u2", "ws-c", "comment", "2025-07-11T09:00:00Z"),
            _event("u4", "ws-d", "login",   "2025-06-10T16:00:00Z"),  # ws-d continues (out-of-order ts ignored for gap calc)
        ]
        summaries = list(agg.process(batch3))
        assert summaries == []  # ws-c ignored, ws-d still active

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("already-terminated" in w and "ws-c" in w for w in warnings)

        # -- Batch 4: ws-d terminates (gap > 30 days) ---------------------------
        # latest_ts for ws-d = 2025-06-10 (from batch3, out-of-order event is newer than 2025-06-03)
        # new event = 2025-07-15; gap = 35 days > 30 → terminate
        batch4 = [
            _event("u3", "ws-d", "logout", "2025-07-15T12:00:00Z"),
        ]
        summaries = list(agg.process(batch4))
        assert len(summaries) == 1

        s_d = summaries[0]
        assert s_d["workspace_id"] == "ws-d"
        assert s_d["user_count"] == 2        # u3, u4 (u4 added in batch3)
        assert s_d["action_count"] == 3      # 3 events total (login, purchase, login) — only 2 unique actions
        assert s_d["pro_subscription_count"] == 1

        # Final sanity: 2 summaries total across all batches
        all_summaries = [s_c, s_d]
        assert len(all_summaries) == 2
