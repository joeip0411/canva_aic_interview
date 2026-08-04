# Active Users — Event Stream Processor

## 1. Problem Statement

Different teams compute "active users" inconsistently, producing mismatched dashboards. This task is to build a Python program that ingests a stream of user-activity events and outputs a single, consistent daily count of active users.

---

## 2. Definitions & Rules

| Term | Definition |
|---|---|
| **Active user** | Any `user_id` that appears in the event stream (at least once) within the daily window. |
| **Daily window** | A calendar day (midnight to midnight). The window is derived from each event's `datetime` field. |
| **Unbounded stream** | The event stream has no fixed end; the processor must handle events arriving continuously. |

### 2.1 Validation Rule

If schema validation fails for an event, **discard that event** — it must not contribute to the active-user calculation.

---

## 3. Data Schemas

### 3.1 Input Event

| Field | Type | Description |
|---|---|---|
| `user_id` | `str` | Unique identifier for the user. |
| `datetime` | `str` | ISO-8601 timestamp (e.g. `2026-08-04T14:30:00`). |
| `activity_type` | `str` | The kind of activity performed (e.g. `login`, `click`, `purchase`). |

All three fields are **required**. Any event missing a field or with a wrong type is invalid.

### 3.2 Output Record

| Field | Type | Description |
|---|---|---|
| `date` | `str` | Calendar date in `YYYY-MM-DD` format. |
| `active_users` | `int` | Number of distinct `user_id` values seen on that date. |

---

## 4. Scope

### 4.1 Core (required)

- **`Event` class** — validates incoming events against the input schema using Pydantic.
- **`StreamProcessor` class** — receives validated events, computes daily distinct active users, and stores results in an instance dictionary.

### 4.2 Stretch Goal (optional)

- Load the output data into a **Pandas DataFrame** and print it.

---

## 5. Technical Guardrails

| Concern | Tool / Library |
|---|---|
| Schema validation | **Pydantic** |
| Testing | **Pytest** |
| Everything else | **Python standard library only** |

---

## 6. Production Readiness (Definition of Done)

1. **Core scope** is fully implemented.
2. **Unit tests** cover every public method.
3. **Integration test** verifies the pipeline end-to-end (raw events in → daily counts out).

---

## 7. Example

**Input stream:**

```json
{"user_id": "u1", "datetime": "2026-08-04T09:00:00", "activity_type": "login"}
{"user_id": "u2", "datetime": "2026-08-04T10:00:00", "activity_type": "click"}
{"user_id": "u1", "datetime": "2026-08-04T11:00:00", "activity_type": "purchase"}
{"user_id": "bad", "datetime": 12345, "activity_type": "login"}
{"user_id": "u3", "datetime": "2026-08-05T08:00:00", "activity_type": "login"}
```

**Expected output:**

| date | active_users |
|---|---|
| 2026-08-04 | 2 |
| 2026-08-05 | 1 |

> The fourth event is discarded because `datetime` is not a `str`. `u1` appears twice on 2026-08-04 but is counted once.
