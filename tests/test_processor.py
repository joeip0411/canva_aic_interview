from pipeline.processor import Processor


class TestProcessorIntegration:
    """Integration tests for the Processor class — stream processing end-to-end."""

    def test_processes_valid_events_and_counts_correctly(self) -> None:
        """Process a stream of valid events and verify daily_counts output."""
        processor = Processor()

        stream: list[dict] = [
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T10:00:00"},
            {"user_id": "bob", "event_type": "view", "event_timestamp": "2026-08-03T11:00:00"},
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T12:00:00"},
        ]

        for idx in range(len(stream)):
            result = processor.process(stream, idx)
            assert result is not None

        assert processor.daily_counts == {
            "2026-08-03": {"alice": 2, "bob": 1},
        }

    def test_skips_invalid_events_gracefully(self) -> None:
        """Invalid events should return None without crashing or affecting counts."""
        processor = Processor()

        stream: list[dict] = [
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T10:00:00"},
            # Invalid: empty user_id
            {"user_id": "", "event_type": "click", "event_timestamp": "2026-08-03T11:00:00"},
            {"user_id": "bob", "event_type": "view", "event_timestamp": "2026-08-03T12:00:00"},
            # Invalid: bad timestamp
            {"user_id": "charlie", "event_type": "view", "event_timestamp": "not-a-date"},
            # Invalid: missing event_type
            {"user_id": "dave", "event_timestamp": "2026-08-03T13:00:00"},
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T14:00:00"},
        ]

        results = []
        for idx in range(len(stream)):
            results.append(processor.process(stream, idx))

        # Valid events at indices 0, 2, 5 should return Event objects
        assert results[0] is not None
        assert results[1] is None  # invalid: empty user_id
        assert results[2] is not None
        assert results[3] is None  # invalid: bad timestamp
        assert results[4] is None  # invalid: missing event_type
        assert results[5] is not None

        # Only valid events counted
        assert processor.daily_counts == {
            "2026-08-03": {"alice": 2, "bob": 1},
        }

    def test_closes_window_when_event_is_24h_past_date(self) -> None:
        """A day-2 event >= 24h after day 1 midnight closes the day 1 window."""
        processor = Processor()

        stream: list[dict] = [
            # Day 1: 2026-08-03
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T10:00:00"},
            {"user_id": "bob", "event_type": "view", "event_timestamp": "2026-08-03T11:00:00"},
            # Day 2: 2026-08-04T00:00:01 is >= 24h after midnight of 2026-08-03
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-04T00:00:01"},
        ]

        for idx in range(len(stream)):
            processor.process(stream, idx)

        # Day 1 window should be closed and moved to result
        assert processor.result == {
            "2026-08-03": {"alice": 1, "bob": 1},
        }
        # Day 2 is the current open window
        assert processor.daily_counts == {
            "2026-08-04": {"alice": 1},
        }

    def test_discards_events_for_already_closed_date(self) -> None:
        """An event for a date that has been closed should be discarded."""
        processor = Processor()

        stream: list[dict] = [
            # Day 1
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T10:00:00"},
            # Day 2 — closes day 1
            {"user_id": "bob", "event_type": "view", "event_timestamp": "2026-08-04T00:00:01"},
            # Stale: this event is for the already-closed day 1
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T14:00:00"},
        ]

        results = []
        for idx in range(len(stream)):
            results.append(processor.process(stream, idx))

        # First two events processed successfully
        assert results[0] is not None
        assert results[1] is not None
        # Third event discarded — its date is already closed
        assert results[2] is None

        # Day 1 counts should be frozen (the stale event was NOT counted)
        assert processor.result == {
            "2026-08-03": {"alice": 1},
        }
        assert processor.daily_counts == {
            "2026-08-04": {"bob": 1},
        }

    def test_full_stream_end_to_end(self) -> None:
        """End-to-end: valid, invalid, window-close, and discard all in one stream."""
        processor = Processor()

        stream: list[dict] = [
            # --- Day 1: 2026-08-03 ---
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T10:00:00"},
            {"user_id": "bob", "event_type": "view", "event_timestamp": "2026-08-03T11:00:00"},
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T12:00:00"},
            # Invalid: empty user_id
            {"user_id": "", "event_type": "click", "event_timestamp": "2026-08-03T13:00:00"},
            # --- Day 2: 2026-08-04 (closes day 1) ---
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-04T00:00:01"},
            {"user_id": "bob", "event_type": "click", "event_timestamp": "2026-08-04T08:00:00"},
            # Invalid: bad timestamp
            {"user_id": "charlie", "event_type": "view", "event_timestamp": "not-a-date"},
            # Stale: day 1 is already closed — should be discarded
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T14:00:00"},
            # Invalid: not a dict at all (simulated as empty dict for graceful handling)
            {},
            # --- Day 3: 2026-08-05 (closes day 2) ---
            {"user_id": "alice", "event_type": "view", "event_timestamp": "2026-08-05T00:00:01"},
            {"user_id": "bob", "event_type": "view", "event_timestamp": "2026-08-05T09:00:00"},
        ]

        results = []
        for idx in range(len(stream)):
            results.append(processor.process(stream, idx))

        # Valid events: indices 0,1,2,4,5,9,10 = 7 events
        valid_count = sum(1 for r in results if r is not None)
        assert valid_count == 7

        # Invalid/skipped: indices 3 (empty user_id), 6 (bad timestamp), 8 (empty dict) = 3
        # Discarded: index 7 (stale day 1 event) = 1
        none_count = sum(1 for r in results if r is None)
        assert none_count == 4

        # Result (closed windows): day 1 and day 2
        assert processor.result == {
            "2026-08-03": {"alice": 2, "bob": 1},
            "2026-08-04": {"alice": 1, "bob": 1},
        }

        # Daily counts (open window): day 3
        assert processor.daily_counts == {
            "2026-08-05": {"alice": 1, "bob": 1},
        }

    def test_index_out_of_bounds_returns_none(self) -> None:
        """An out-of-bounds index should return None gracefully."""
        processor = Processor()

        stream: list[dict] = [
            {"user_id": "alice", "event_type": "click", "event_timestamp": "2026-08-03T10:00:00"},
        ]

        # Index equal to length (1 past the end)
        assert processor.process(stream, 1) is None

        # Index well beyond length
        assert processor.process(stream, 5) is None

        # Valid index should still work
        assert processor.process(stream, 0) is not None
