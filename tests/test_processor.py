from pydantic import ValidationError

from src.experiment.event import Event
from src.experiment.processor import Processor


# -- helpers ----------------------------------------------------------------

def _event(user_id, experiment_id, variant_id, timestamp, event_type="exposure"):
    """Shorthand for creating an Event with minimal boilerplate."""
    return Event(
        user_id=user_id,
        experiment_id=experiment_id,
        variant_id=variant_id,
        timestamp=timestamp,
        event_type=event_type,
    )


# -- happy path -------------------------------------------------------------


def test_single_user_single_variant():
    """One user, one experiment, one variant → 100% integrity."""
    processor = Processor()
    events = [
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        _event("u1", "exp1", "control", "2025-01-16T10:00:00"),
        _event("u1", "exp1", "control", "2025-01-17T10:00:00"),
    ]
    results = processor.process(events)

    assert len(results) == 1
    assert results[0]["user_id"] == "u1"
    assert results[0]["experiment_id"] == "exp1"
    assert results[0]["experiment_integrity"] == {"control": 1.0}


def test_multiple_users_clean_data():
    """Multiple users, each sees only one variant → all 100% integrity."""
    processor = Processor()
    events = [
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        _event("u2", "exp1", "treatment", "2025-01-15T10:00:00"),
    ]
    results = processor.process(events)

    assert len(results) == 2
    assert results[0]["experiment_integrity"] == {"control": 1.0}
    assert results[1]["experiment_integrity"] == {"treatment": 1.0}


# -- polluted data (integrity violations) -----------------------------------


def test_user_sees_multiple_variants():
    """User exposed to two variants → percentages reflect the split."""
    processor = Processor()
    events = [
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        _event("u1", "exp1", "control", "2025-01-16T10:00:00"),
        _event("u1", "exp1", "treatment", "2025-01-17T10:00:00"),
    ]
    results = processor.process(events)

    assert len(results) == 1
    integrity = results[0]["experiment_integrity"]
    assert integrity == {"control": round(2 / 3, 4), "treatment": round(1 / 3, 4)}


def test_mixed_clean_and_polluted():
    """Some users are clean, others have conflicting variants."""
    processor = Processor()
    events = [
        # u1 — clean (control only)
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        _event("u1", "exp1", "control", "2025-01-16T10:00:00"),
        # u2 — polluted (two variants)
        _event("u2", "exp1", "control", "2025-01-15T10:00:00"),
        _event("u2", "exp1", "treatment", "2025-01-16T10:00:00"),
    ]
    results = processor.process(events)

    u1 = next(r for r in results if r["user_id"] == "u1")
    u2 = next(r for r in results if r["user_id"] == "u2")
    assert u1["experiment_integrity"] == {"control": 1.0}
    assert u2["experiment_integrity"] == {"control": 0.5, "treatment": 0.5}


# -- window filtering -------------------------------------------------------


def test_events_outside_window_are_dropped():
    """Events past the 3-month window are excluded."""
    processor = Processor()
    events = [
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        # This event is ~6 months later — outside the default 3-month window.
        _event("u1", "exp1", "treatment", "2025-07-20T10:00:00"),
    ]
    results = processor.process(events)

    # Only the first event counts → 100% control.
    assert results[0]["experiment_integrity"] == {"control": 1.0}


def test_custom_window_months():
    """A shorter window drops more events."""
    processor = Processor(window_months=1)
    events = [
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        # 2 months later — outside a 1-month window.
        _event("u1", "exp1", "treatment", "2025-03-20T10:00:00"),
    ]
    results = processor.process(events)

    assert results[0]["experiment_integrity"] == {"control": 1.0}


# -- edge cases -------------------------------------------------------------


def test_empty_event_list():
    """No events → empty result list."""
    processor = Processor()
    assert processor.process([]) == []


def test_multiple_experiments_independent_windows():
    """Each experiment has its own 3-month window."""
    processor = Processor()
    events = [
        # exp1 starts Jan 2025 → window closes Apr 2025.
        _event("u1", "exp1", "control", "2025-01-15T10:00:00"),
        # exp2 starts Jun 2025 → window closes Sep 2025.
        _event("u2", "exp2", "treatment", "2025-06-15T10:00:00"),
        # exp1 event still in window (Feb 2025).
        _event("u1", "exp1", "control", "2025-02-15T10:00:00"),
        # exp2 event outside its window (Dec 2025, past Sep).
        _event("u2", "exp2", "treatment_b", "2025-12-15T10:00:00"),
    ]
    results = processor.process(events)

    # u1/exp1: both Jan + Feb events → 100% control.
    u1 = next(r for r in results if r["user_id"] == "u1")
    assert u1["experiment_integrity"] == {"control": 1.0}

    # u2/exp2: only the Jun event within window → 100% treatment.
    u2 = next(r for r in results if r["user_id"] == "u2")
    assert u2["experiment_integrity"] == {"treatment": 1.0}


# -- malformed data resilience ---------------------------------------------


def test_malformed_events_dropped_before_processing():
    """Invalid raw entries are caught at the Event boundary and skipped.

    The Processor only ever sees valid Events, so malformed rows in the
    raw stream must be filtered out during Event construction — they are
    never passed to ``process()``.  The calculation still produces the
    correct result from the surviving valid events.
    """
    processor = Processor()
    raw_rows = [
        # Valid — u1 sees "control" twice.
        {"user_id": "u1", "experiment_id": "exp1", "variant_id": "control",
         "timestamp": "2025-01-15T10:00:00", "event_type": "exposure"},
        # Malformed — empty user_id; dropped.
        {"user_id": "", "experiment_id": "exp1", "variant_id": "control",
         "timestamp": "2025-01-15T10:00:00", "event_type": "exposure"},
        # Malformed — invalid timestamp; dropped.
        {"user_id": "u1", "experiment_id": "exp1", "variant_id": "control",
         "timestamp": "not-a-date", "event_type": "exposure"},
        # Malformed — missing experiment_id; dropped.
        {"user_id": "u1", "variant_id": "control",
         "timestamp": "2025-01-15T10:00:00", "event_type": "exposure"},
        # Valid — u1 sees "control" again.
        {"user_id": "u1", "experiment_id": "exp1", "variant_id": "control",
         "timestamp": "2025-01-16T10:00:00", "event_type": "exposure"},
    ]

    # Construct Events, dropping anything that fails validation.
    valid_events: list[Event] = []
    for row in raw_rows:
        try:
            valid_events.append(Event(**row))
        except ValidationError:
            continue  # malformed — discard gracefully

    # 3 of 5 rows were malformed → only 2 valid events remain.
    assert len(valid_events) == 2

    results = processor.process(valid_events)

    assert len(results) == 1
    assert results[0]["experiment_integrity"] == {"control": 1.0}
