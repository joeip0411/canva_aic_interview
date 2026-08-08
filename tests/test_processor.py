from __future__ import annotations

from pipeline.processor import Processor

# =========================================================================
# Helpers
# =========================================================================

def _process_all(processor: Processor, events: list[dict]) -> list[object]:
    """Run every event through the processor and return accepted events."""
    return [processor.process(events, i) for i in range(len(events))]


def _valid_event(**overrides: str) -> dict[str, str]:
    """Return a minimal valid raw event dict."""
    return {
        "user_id": "user-1",
        "product_id": "product-a",
        "event_timestamp": "2026-08-08T10:30:00",
        "event_type": "click",
        **overrides,
    }


# =========================================================================
# Happy path — all valid events
# =========================================================================

class TestHappyPath:
    def test_single_product_single_date(self) -> None:
        proc = Processor()
        events = [
            _valid_event(),
            _valid_event(),
            _valid_event(),
            # Advance past the 48-hour window (2026-08-08 + 3 days = 2026-08-11).
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        results = _process_all(proc, events)
        assert all(r is not None for r in results)
        assert proc.summary == {"product-a": {"2026-08-08": 3}}
        assert "2026-08-08" in proc.closed_dates

    def test_multiple_products_multiple_dates(self) -> None:
        proc = Processor()
        events = [
            # Day 1 — two products
            _valid_event(product_id="p1", event_timestamp="2026-08-08T09:00:00"),
            _valid_event(product_id="p1", event_timestamp="2026-08-08T10:00:00"),
            _valid_event(product_id="p2", event_timestamp="2026-08-08T11:00:00"),
            # Day 2 — one product
            _valid_event(product_id="p1", event_timestamp="2026-08-09T09:00:00"),
            # Advance past day-1 window (2026-08-11 00:00).
            _valid_event(product_id="p2", event_timestamp="2026-08-11T00:00:00"),
        ]
        _process_all(proc, events)
        # Only 08/08 should be finalised (08/09 window still open).
        assert proc.summary == {
            "p1": {"2026-08-08": 2},
            "p2": {"2026-08-08": 1},
        }
        assert "2026-08-08" in proc.closed_dates
        assert "2026-08-09" not in proc.closed_dates


# =========================================================================
# Invalid events are gracefully dropped
# =========================================================================

class TestInvalidEventsDropped:
    def test_empty_user_id_dropped(self) -> None:
        proc = Processor()
        events = [
            _valid_event(user_id="  "),   # whitespace-only → invalid
            _valid_event(),                # valid
            _valid_event(user_id=""),      # empty → invalid
            # Close the window
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        results = _process_all(proc, events)
        assert results[0] is None
        assert results[1] is not None
        assert results[2] is None
        assert results[3] is not None
        assert proc.summary == {"product-a": {"2026-08-08": 1}}

    def test_bad_timestamp_dropped(self) -> None:
        proc = Processor()
        events = [
            _valid_event(event_timestamp="not-a-date"),  # invalid
            _valid_event(),                               # valid
            _valid_event(event_timestamp=""),             # empty → invalid
            # Close the window
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        results = _process_all(proc, events)
        assert results[0] is None
        assert results[1] is not None
        assert results[2] is None
        assert proc.summary == {"product-a": {"2026-08-08": 1}}

    def test_missing_field_dropped(self) -> None:
        proc = Processor()
        events: list[dict] = [
            {"user_id": "u1", "product_id": "p1",
             "event_timestamp": "2026-08-08T10:00:00"},  # missing event_type
            _valid_event(),                                # valid
            # Close the window
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        results = _process_all(proc, events)
        assert results[0] is None
        assert results[1] is not None
        assert proc.summary == {"product-a": {"2026-08-08": 1}}


# =========================================================================
# Out-of-order events
# =========================================================================

class TestOutOfOrderEvents:
    def test_out_of_order_within_window(self) -> None:
        """Events arrive in non-chronological order but all within the
        same daily window — every one should be counted."""
        proc = Processor()
        events = [
            _valid_event(event_timestamp="2026-08-08T12:00:00"),
            _valid_event(event_timestamp="2026-08-08T09:00:00"),  # earlier
            _valid_event(event_timestamp="2026-08-08T15:00:00"),  # later
            # Close the window
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        results = _process_all(proc, events)
        assert all(r is not None for r in results)
        assert proc.summary == {"product-a": {"2026-08-08": 3}}

    def test_out_of_order_late_arrival_within_grace_period(self) -> None:
        """A late-arriving event (older timestamp processed after newer
        ones) is still counted as long as its date's 48-hour window is
        open."""
        proc = Processor()
        events = [
            # Two events for 08/08.
            _valid_event(event_timestamp="2026-08-08T09:00:00"),
            _valid_event(event_timestamp="2026-08-08T10:00:00"),
            # A newer event for 08/09 advances latest_ts.
            _valid_event(event_timestamp="2026-08-09T12:00:00"),
            # Late arrival: another 08/08 event, ts=08/08T15:00 (older
            # than latest_ts=08/09T12:00).  Its date is 08/08 which is
            # still open → should be counted.
            _valid_event(event_timestamp="2026-08-08T15:00:00",
                         event_type="late_click"),
            # Advance past 08/08 window; 08/08+3 = 08/11 00:00.
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        results = _process_all(proc, events)
        assert all(r is not None for r in results)
        # Only 08/08 is finalised (08/09 window still open, 08/11 no events).
        assert proc.summary == {"product-a": {"2026-08-08": 3}}


# =========================================================================
# Window closure — late events discarded
# =========================================================================

class TestWindowClosure:
    def test_late_event_discarded_after_window_closes(self) -> None:
        """Once the 48-hour window shuts, further events for that day are
        silently dropped."""
        proc = Processor()
        events = [
            _valid_event(event_timestamp="2026-08-08T09:00:00"),
            _valid_event(event_timestamp="2026-08-08T10:00:00"),
            # This event pushes latest_ts past the 08/08 deadline.
            _valid_event(event_timestamp="2026-08-11T00:00:01"),
            # Too late — 08/08 window is closed.  Event timestamp is on
            # 08/08 (older than latest_ts, so latest_ts doesn't move).
            _valid_event(event_timestamp="2026-08-08T23:59:59",
                         event_type="doomed"),
        ]
        results = _process_all(proc, events)
        assert results[0] is not None
        assert results[1] is not None
        assert results[2] is not None
        assert results[3] is None  # discarded
        assert proc.summary == {"product-a": {"2026-08-08": 2}}
        assert "2026-08-08" in proc.closed_dates

    def test_edge_case_first_event_too_late(self) -> None:
        """The very first event for a date arrives after its window would
        have already closed (based on latest_ts from other dates)."""
        proc = Processor()
        # Establish a latest_ts well past 08/08's deadline (08/11 00:00).
        proc.process(
            [_valid_event(event_timestamp="2026-08-12T00:00:00")], 0
        )
        # Now an event whose timestamp falls on 08/08 — deadline was
        # 08/11 00:00, already past.  Should be discarded immediately.
        result = proc.process(
            [_valid_event(event_timestamp="2026-08-08T01:00:00",
                          event_type="too_late")], 0
        )
        assert result is None
        assert "2026-08-08" in proc.closed_dates

    def test_window_closes_multiple_dates_at_once(self) -> None:
        """A large timestamp jump can close several daily windows in one
        pass."""
        proc = Processor()
        events = [
            _valid_event(event_timestamp="2026-08-08T09:00:00"),
            _valid_event(event_timestamp="2026-08-09T09:00:00"),
            _valid_event(event_timestamp="2026-08-10T09:00:00"),
            # Jump past all three deadlines at once.
            # 08/08 → 08/11, 08/09 → 08/12, 08/10 → 08/13
            _valid_event(event_timestamp="2026-08-13T00:00:00"),
        ]
        _process_all(proc, events)
        assert proc.closed_dates == {"2026-08-08", "2026-08-09", "2026-08-10"}
        assert proc.summary == {
            "product-a": {
                "2026-08-08": 1,
                "2026-08-09": 1,
                "2026-08-10": 1,
            },
        }


# =========================================================================
# Summary vs open data separation
# =========================================================================

class TestSummarySeparation:
    def test_summary_excludes_open_dates(self) -> None:
        """``summary`` returns only finalised data; in-flight dates stay
        in ``open_summary``."""
        proc = Processor()
        events = [
            _valid_event(event_timestamp="2026-08-08T09:00:00"),
            _valid_event(event_timestamp="2026-08-09T09:00:00"),
            # Close only 08/08 (deadline 08/11).
            _valid_event(event_timestamp="2026-08-11T00:00:00"),
        ]
        _process_all(proc, events)
        # Finalised: only 08/08.
        assert proc.summary == {"product-a": {"2026-08-08": 1}}
        # Still open: 08/09 and 08/11 (the closing event itself).
        assert proc.open_summary == {
            "product-a": {"2026-08-09": 1, "2026-08-11": 1},
        }

    def test_empty_summary_when_no_windows_closed(self) -> None:
        proc = Processor()
        events = [
            _valid_event(event_timestamp="2026-08-08T09:00:00"),
            _valid_event(event_timestamp="2026-08-08T10:00:00"),
        ]
        _process_all(proc, events)
        # No window closed yet — summary is empty.
        assert proc.summary == {}
        assert proc.open_summary == {"product-a": {"2026-08-08": 2}}
