# Workspace Health Evaluation — Python Module

## 1. Problem Statement

A new feature allows individual users to upgrade their personal account into a **Team Workspace** and invite collaborators. Raw JSON logs of these workspace actions are captured in an event stream. Build a Python module that evaluates the **health of each workspace** so the product team can:

- Identify patterns that drive team expansion.
- Spot high-value accounts.

---

## 2. Data Model

### 2.1 Input: `Event`

A single raw event from the stream, representing one workspace action.

| Field              | Type   | Description                                |
|--------------------|--------|--------------------------------------------|
| `user_id`          | `str`  | ID of the user who performed the action.   |
| `workspace_id`     | `str`  | ID of the workspace the action belongs to. |
| `action`           | `str`  | Action name (e.g. `"purchase_pro_subscription"`). |
| `event_timestamp`  | `str`  | ISO‑8601 UTC timestamp of when the action occurred. |
| `metadata`         | `dict` | Arbitrary key-value pairs with extra context about the event. |

### 2.2 Output: `WorkspaceSummary`

One summary row per **workspace session** (see §3).

| Field                      | Type  | Description                                              |
|----------------------------|-------|----------------------------------------------------------|
| `workspace_id`             | `str` | The workspace this summary belongs to.                    |
| `user_count`               | `int` | Count of **distinct** `user_id` values seen in this workspace's session. |
| `action_count`             | `int` | Total number of events processed for this workspace.      |
| `pro_subscription_count`   | `int` | Count of events where `action == "purchase_pro_subscription"`. |

---

## 3. Session Model

A **session** is the active lifespan of a workspace in the event stream.

- **Session start** — the timestamp of the **first event** received for a workspace (no gap to compare yet).
- **Session termination** — a gap of **more than 30 days** between the *latest event received so far* and the *next incoming event* for the same workspace.
- **One summary per workspace** — once a session is terminated, **no further events** for that workspace are considered (the summary is frozen and the workspace is ignored for the rest of the stream).

> **Rationale**: A gap > 30 days signals that the workspace is no longer active, so it is safe to finalize and emit its summary.

---

## 4. Scope

### 4.1 Core Goals *(required)*

| # | Deliverable | Notes |
|---|-------------|-------|
| 1 | **`Event` class** | Implements the input schema (§2.1). Use Pydantic. |
| 2 | **`WorkspaceSummary` class** | Implements the output schema (§2.2). Use Pydantic. |
| 3 | **`Aggregator` class** | Ingests a stream of `Event` objects, tracks sessions per workspace (§3), and emits `WorkspaceSummary` objects when a session terminates. |

### 4.2 Stretch Goals *(optional)*

| # | Deliverable | Notes |
|---|-------------|-------|
| 4 | **Summary printer** | Functionality to pretty-print the summary stats for each workspace (e.g. to stdout or a log). |

---

## 5. Production Readiness

1. **Core-goal functionality works end-to-end** — events go in, correct summaries come out.
2. **Unit tests** — one test file per class, exercising happy path, edge cases, and error conditions.
3. **Integration test** — a single test that feeds a known sequence of events through the aggregator and asserts the output summaries.
4. **Logging** — meaningful `logging` calls (stdlib `logging` module) at key transitions:
   - Session start (`INFO`).
   - Session termination + summary emission (`INFO`).
   - Invalid or malformed events skipped (`WARNING`).
   - Duplicate workspace IDs for already-terminated sessions (`WARNING`).

---

## 6. Technical Guardrails

| Rule | Detail |
|------|--------|
| **Allowed libraries** | `pydantic` (data modelling / validation), `pytest` (testing). |
| **Everything else** | Standard library only (`logging`, `datetime`, `collections`, `itertools`, `json`, etc.). |
| **Python version** | 3.10+ (so `str | None` union syntax and `datetime.timezone` are available). |

---

## 7. Edge Cases & Clarifications

> *Items marked `[?]` are decisions for the implementer to confirm before coding; the rest are prescriptive.*

1. **Out-of-order events** — events may arrive with timestamps older than the latest seen event for a workspace. The aggregator should still count the event and update `user_count` / `action_count`, but the session-termination gap is always measured from the **latest timestamp seen** for that workspace.
2. **Exactly 30 days** — a gap of *exactly* 30 days (to the second) does **not** terminate the session. The condition is **strictly greater than** 30 days.
3. **Duplicate events** — the aggregator does **not** deduplicate. Every event received is counted.
4. **Timestamp format** — ISO‑8601 UTC (`"2025-07-29T14:30:00Z"`). No other variants expected.
5. **Metadata** — stored on the `Event` model for completeness but not used in any aggregation logic.
6. **Empty workspace** — not a concern. Sessions are only created by the first event, so a zero-event workspace cannot exist.
