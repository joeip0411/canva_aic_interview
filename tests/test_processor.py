"""Integration tests for the Processor class."""

from src.pipeline.processor import Processor
from src.pipeline.schema import Event


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _event(**overrides) -> Event:
    """Build a valid ``Event`` with sensible defaults for every field."""
    defaults = {
        "asset_id": "a1",
        "event_time": "2026-07-01T10:00:00",
        "user_id": "u1",
        "creator_id": "c1",
        "event_type": "view",
    }
    return Event.model_validate({**defaults, **overrides})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestProcessorHappyPath:
    """End-to-end flows with clean, fully-valid data."""

    def test_single_asset_single_user(self) -> None:
        """One asset, one creation event, one usage event."""
        events = [
            _event(asset_id="a1", event_time="2026-06-15T00:00:00",
                   creator_id="c1", event_type="asset_creation"),
            _event(asset_id="a1", event_time="2026-07-01T10:00:00",
                   user_id="u1", creator_id="c1", event_type="view"),
        ]

        output = Processor().process(events)

        assert output["a1"] == {
            "asset_id": "a1",
            "creator_id": "c1",
            "unique_user_count": 1,
            "total_usage_count": 1,
        }

    def test_single_asset_multiple_users(self) -> None:
        """One asset used by many distinct users."""
        events = [
            _event(asset_id="a1", event_time="2026-06-01T00:00:00",
                   creator_id="c1", event_type="asset_creation"),
            *[_event(asset_id="a1", user_id=uid, creator_id="c1", event_type="use")
              for uid in ("u1", "u2", "u3")],
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 3
        assert output["a1"]["unique_user_count"] == 3

    def test_single_asset_repeat_user(self) -> None:
        """Repeated user counts once toward unique_users."""
        events = [
            _event(event_time="2026-06-01T00:00:00", event_type="asset_creation"),
            *[_event() for _ in range(5)],  # same u1, 5 times
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 5
        assert output["a1"]["unique_user_count"] == 1

    def test_multiple_assets_different_creators(self) -> None:
        """Two assets, different creators — no cross-contamination."""
        events = [
            _event(asset_id="a1", event_time="2026-06-01T00:00:00",
                   creator_id="c_alpha", event_type="asset_creation"),
            _event(asset_id="a1", creator_id="c_alpha", user_id="u1"),
            _event(asset_id="a2", event_time="2026-06-15T00:00:00",
                   creator_id="c_beta", event_type="asset_creation"),
            _event(asset_id="a2", creator_id="c_beta", user_id="u2", event_type="remix"),
            _event(asset_id="a2", creator_id="c_beta", user_id="u3", event_type="use"),
        ]

        output = Processor().process(events)

        assert output["a1"]["creator_id"] == "c_alpha"
        assert output["a1"]["total_usage_count"] == 1
        assert output["a1"]["unique_user_count"] == 1

        assert output["a2"]["creator_id"] == "c_beta"
        assert output["a2"]["total_usage_count"] == 2
        assert output["a2"]["unique_user_count"] == 2

    def test_creation_event_not_counted(self) -> None:
        """asset_creation must not appear in engagement metrics."""
        events = [
            _event(event_time="2026-06-01T00:00:00", user_id="c1",
                   event_type="asset_creation"),
            _event(),
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 1
        assert output["a1"]["unique_user_count"] == 1  # c1 NOT included

    def test_empty_stream(self) -> None:
        """An empty iterable produces an empty result dict."""
        output = Processor().process([])
        assert output == {}


# ---------------------------------------------------------------------------
# Tracking window
# ---------------------------------------------------------------------------

class TestProcessorTrackingWindow:
    """3‑month window enforcement via ``process()``."""

    def test_event_inside_window(self) -> None:
        """Event exactly 3 months after creation, end of day — in window."""
        events = [
            _event(event_time="2026-03-15T08:00:00", event_type="asset_creation"),
            _event(event_time="2026-06-15T23:59:59", user_id="u1"),
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 1

    def test_event_outside_window(self) -> None:
        """Event 1 second past the window end — dropped."""
        events = [
            _event(event_time="2026-03-15T08:00:00", event_type="asset_creation"),
            _event(event_time="2026-06-16T00:00:00", user_id="u1"),
        ]

        output = Processor().process(events)

        assert "a1" not in output

    def test_event_before_creation_known(self) -> None:
        """Usage events arriving before the creation event are allowed."""
        events = [
            _event(event_time="2026-07-01T10:00:00", user_id="u1"),
            _event(event_time="2026-06-15T00:00:00", event_type="asset_creation"),
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 1

    def test_window_month_overflow(self) -> None:
        """Creation in October — window ends correctly in January."""
        events = [
            _event(event_time="2026-10-15T08:00:00", event_type="asset_creation"),
            _event(event_time="2027-01-15T12:00:00", user_id="u1"),
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 1

    def test_window_day_clamped(self) -> None:
        """Jan 31 creation → window ends Apr 30 (April has 30 days)."""
        events = [
            _event(event_time="2026-01-31T08:00:00", event_type="asset_creation"),
            _event(event_time="2026-04-30T23:59:59", user_id="u1"),
        ]

        output = Processor().process(events)

        assert output["a1"]["total_usage_count"] == 1


# ---------------------------------------------------------------------------
# Mixed good and bad data
# ---------------------------------------------------------------------------

class TestProcessorMixedData:
    """Real-world stream where some events are discarded by business rules
    and only valid in-window usage events contribute to the output."""

    def test_mixed_good_and_out_of_window(self) -> None:
        """Out-of-window events are silently dropped; good events prevail."""
        events = [
            # Good — creation
            _event(asset_id="a1", event_time="2026-06-01T00:00:00",
                   creator_id="c1", event_type="asset_creation"),
            # Good — usage u1 within window
            _event(asset_id="a1", event_time="2026-07-01T10:00:00",
                   user_id="u1", event_type="view"),
            # Bad — outside window (Oct = month 5, window ended Sep 1)
            _event(asset_id="a1", event_time="2026-10-15T10:00:00",
                   user_id="u_ghost", event_type="view"),
            # Good — usage u2 within window
            _event(asset_id="a1", event_time="2026-08-15T10:00:00",
                   user_id="u2", event_type="use"),
            # Bad — duplicate creation (should be captured but not counted)
            _event(asset_id="a1", event_time="2026-06-01T00:00:00",
                   creator_id="c1", event_type="asset_creation"),
            # Good — usage u3 within window
            _event(asset_id="a1", event_time="2026-07-20T10:00:00",
                   user_id="u3", event_type="remix"),
            # Bad — outside window (next year)
            _event(asset_id="a1", event_time="2027-01-01T00:00:00",
                   user_id="u_ghost2", event_type="use"),
            # Good — repeat u1
            _event(asset_id="a1", event_time="2026-08-01T10:00:00",
                   user_id="u1", event_type="use"),
        ]

        output = Processor().process(events)

        assert output["a1"]["creator_id"] == "c1"
        # 4 good usage events: u1, u2, u3, u1(repeat) = 4 total
        assert output["a1"]["total_usage_count"] == 4
        # 3 unique users: u1, u2, u3 — ghosts excluded
        assert output["a1"]["unique_user_count"] == 3
