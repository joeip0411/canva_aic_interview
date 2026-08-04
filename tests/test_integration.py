from datetime import datetime

import pytest
from pydantic import ValidationError

from src.pipeline.event import Event
from src.pipeline.stream_processor import StreamProcessor


def _build_events(raw_events: list[dict]) -> list[Event]:
    """Convert raw dicts to Event objects, silently discarding invalid ones."""
    valid: list[Event] = []
    for raw in raw_events:
        try:
            valid.append(Event(**raw))
        except ValidationError:
            pass
    return valid


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

def test_pipeline_raw_dicts_to_daily_counts() -> None:
    """End-to-end: raw dicts → Event validation → StreamProcessor → counts.

    Invalid dicts are discarded. Valid events are bucketed by day with
    deduplication. Days far enough apart trigger stale-day closing.
    """
    raw_events: list[dict] = [
        # --- Day 2026-08-01 (2 distinct users: u1, u2) ---
        {"user_id": "u1", "datetime": "2026-08-01T08:00:00", "activity_type": "login"},
        {"user_id": "u2", "datetime": "2026-08-01T09:00:00", "activity_type": "click"},
        {"user_id": "u1", "datetime": "2026-08-01T10:00:00", "activity_type": "purchase"},  # duplicate
        # --- Invalid — missing user_id ---
        {"datetime": "2026-08-01T11:00:00", "activity_type": "login"},
        # --- Invalid — blank user_id ---
        {"user_id": "   ", "datetime": "2026-08-01T12:00:00", "activity_type": "login"},
        # --- Invalid — unparseable datetime ---
        {"user_id": "u99", "datetime": "garbage", "activity_type": "login"},
        # --- Invalid — wrong type for activity_type ---
        {"user_id": "u3", "datetime": "2026-08-01T13:00:00", "activity_type": 123},
        # --- Day 2026-08-02 (1 distinct user: u3) ---
        {"user_id": "u3", "datetime": "2026-08-02T08:00:00", "activity_type": "login"},
        # --- Day 2026-08-04 (far enough to close days 1 & 2) ---
        {"user_id": "u1", "datetime": "2026-08-04T08:00:00", "activity_type": "login"},
        {"user_id": "u4", "datetime": "2026-08-04T09:00:00", "activity_type": "click"},
    ]

    events = _build_events(raw_events)

    # 10 raw dicts → 4 invalid discarded → 6 valid events remain
    assert len(events) == 6

    processor = StreamProcessor()
    processor.process(events)

    results = processor.flush_results()

    # 2026-08-04 is still open (its midnight + 24h = 2026-08-05 > max_ts)
    # 2026-08-01 and 2026-08-02 are closed
    assert results == {
        "2026-08-01": 2,  # u1, u2
        "2026-08-02": 1,  # u3
    }

    # Second flush returns empty (nothing newly closed)
    assert processor.flush_results() == {}
