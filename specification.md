# Sessionisation & AI Feature Attribution

## Problem Statement

Canva's product team wants to analyze user behavior during "design sessions." They need a Python module that takes a stream of raw user interaction events, groups them into distinct sessions based on an inactivity threshold, and attributes whether each session was "AI-Enhanced."

### Session Definition

A **session** is a sequence of events from the **same user** where the gap between any two consecutive events does **not** exceed 30 minutes. If the gap exceeds 30 minutes, the later event starts a new session.

### AI-Enhanced Attribution

A session is `is_ai_enhanced = true` if **at least one** event in that session has `event_type == "use_ai_magic"`. Otherwise, `is_ai_enhanced = false`.

### Stale Event Handling

Any event whose `timestamp` is more than 30 minutes in the past relative to the time of processing (i.e., `now - event.timestamp > 30 min`) is discarded and does not contribute to any session.

### Scale

Event volume is expected to be large (Canva scale). The implementation must process events as a **stream** — do not accumulate all events or sessions in memory.

---

## Data Schemas

### Input: Raw Event

```json
{"user_id": "user_123", "timestamp": "2026-03-01T10:00:00Z", "event_type": "create_design", "meta": {"platform": "web"}}
```

| Field        | Type   | Required | Notes                                     |
| ------------ | ------ | -------- | ----------------------------------------- |
| `user_id`    | string | yes      | Non-empty                                 |
| `timestamp`  | string | yes      | ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`)     |
| `event_type` | string | yes      | Non-empty, snake_case                     |
| `meta`       | object | yes      | Arbitrary key-value pairs; can be empty `{}` |

### Output: Session Summary

| Field            | Type    | Description                                                       |
| ---------------- | ------- | ----------------------------------------------------------------- |
| `session_id`     | string  | `"{user_id}{session_start}{session_end}"` (concatenated, no delimiter) |
| `user_id`        | string  | The user this session belongs to                                  |
| `session_start`  | timestamp | ISO-8601 timestamp of the **first** event in the session       |
| `session_end`    | timestamp | ISO-8601 timestamp of the **last** event in the session        |
| `total_events`   | int     | Number of events in this session                                  |
| `is_ai_enhanced` | boolean | `true` if at least one event in the session has `event_type == "use_ai_magic"` |

---

## Scope

### Core Deliverables

| Class              | Responsibility                                              |
| ------------------ | ----------------------------------------------------------- |
| `RawEventData`     | Pydantic model that validates each incoming event against the input schema. |
| `OutputSummaryData`| Pydantic model that validates each output record against the output schema. |
| `StreamProcessor`  | Accepts an iterable of raw event dicts, filters out stale events, groups the remainder into sessions, and yields `OutputSummaryData` records. |

### Stretch Goal

- Generate a human-readable summary report from the processed sessions.

---

## Production Readiness

1. All functional requirements above are met.
2. Unit tests and integration tests exist and pass (using `pytest`).
3. Logging is present at key points (discarded stale events, session boundaries, errors) using the standard `logging` module.

---

## Technical Constraints

- **Allowed dependencies**: Pydantic and Pytest. Use the Python standard library for everything else.

---

## Code Style Rules

1. Prioritize **readability** over clever one-liners.
2. All methods must have **type hints** for arguments and return values.
3. Include **inline comments** on complex or non-obvious logic.
4. Every function must do **exactly one thing**.
5. Wrap `try`/`except` blocks **tightly** around the exact lines that can fail — never blanket-wrap an entire function body.
