# Asset Engagement Score — Python Module Specification

## 1. Problem Statement

Canva is launching a new **payout and incentive system** for the Creator Marketplace. Creators upload templates and design elements; users interact with them. A massive raw event-log stream captures every interaction. We need a Python module that calculates an **Asset Engagement Score** for every marketplace asset. This score will be consumed by:

---

## 2. Business Rules

### 2.1 Asset Engagement Score Definition

The score is composed of two metrics, computed per asset:

| Metric                | Definition                                               |
| --------------------- | -------------------------------------------------------- |
| `total_usage_count`  | Total number of interaction events for the asset.        |
| `unique_user_count`  | Number of distinct users who interacted with the asset.  |

### 2.2 Tracking Window

An asset is only tracked for **3 calendar months** from its creation date (the month of creation counts as month 1). Events falling outside this window must be silently ignored during metric computation.

### 2.3 Scale Assumptions

Data volume is at **Canva scale** (billions of events). The implementation must:

- Process events in a **streaming / iterator-based** fashion — never load the full event set into memory.
- Use **constant-memory** data structures where possible (e.g., in-memory dicts are acceptable for the final aggregated results, which are bounded by the number of active assets, not the number of raw events).
- Avoid O(n²) operations on the event stream.

---

## 3. Data Contracts

### 3.1 Input Schema

Each raw event has the following fields:

| Field          | Type     | Required | Description                                    | Validation Rule                  |
| -------------- | -------- | -------- | ---------------------------------------------- | -------------------------------- |
| `asset_id`     | `str`    | Yes      | Unique identifier for the marketplace asset.    | Non-empty string.                |
| `event_time`   | `str`    | Yes      | ISO-8601 UTC timestamp of the interaction.      | Must parse to a valid datetime.  |
| `user_id`      | `str`    | Yes      | Unique identifier for the interacting user.     | Non-empty string.                |
| `creator_id`   | `str`    | Yes      | Unique identifier for the asset's creator.      | Non-empty string.                |
| `event_type`   | `str`    | Yes      | Type of interaction (e.g., `view`, `use`, `remix`). | Non-empty string.                |

### 3.2 Output Schema

Aggregated results per asset, represented as a Python `dict`:

| Field                | Type  | Description                                              |
| -------------------- | ----- | -------------------------------------------------------- |
| `asset_id`           | `str` | The asset identifier.                                    |
| `creator_id`         | `str` | The creator who owns this asset.                         |
| `unique_user_count`  | `int` | Count of distinct `user_id` values seen for this asset.  |
| `total_usage_count`  | `int` | Total number of events received for this asset.          |

**Internal representation**: Use a Python dictionary keyed by `asset_id`, where each value holds the running `creator_id`, a `set` for unique user IDs, and an `int` for the total usage counter.

---

## 4. Functional Requirements (Core)

### 4.1 Input Schema Validation

- Validate every incoming event against the input schema **before** it enters the stream processor.
- Reject (skip) malformed events and **log a warning** with enough detail to diagnose the source (event fields, reason for rejection).
- Validation rules:
  - All required fields must be present and non-`None`.
  - `asset_id`, `user_id`, `creator_id`, `event_type` must be non-empty strings.
  - `event_time` must be a valid ISO‑8601 datetime string.
  - Invalid events must not halt the stream — processing must continue.

### 4.2 Stream Processor

- Accept an **iterable / generator** of raw event dictionaries (one event at a time).
- For each valid event:
  1. Check if the event falls within the asset's 3‑month tracking window.
  2. If within window: increment `total_usage_count` and add `user_id` to the unique‑user set for that `asset_id`.
  3. If outside window: silently skip.
- Return the aggregated results as a dictionary keyed by `asset_id`.

### 4.3 Public API

The module must expose a clean, documented public API:

```python
def calculate_engagement_scores(events: Iterable[dict]) -> dict[str, dict]:
    """
    Process a stream of raw interaction events and return per-asset
    engagement scores.

    Args:
        events: An iterable of raw event dicts (see Input Schema).

    Returns:
        A dict mapping asset_id to:
            {
                "asset_id": str,
                "creator_id": str,
                "unique_user_count": int,
                "total_usage_count": int,
            }
    """
    ...
```

---

## 5. Functional Requirements (Stretch)

### 5.1 Business Reports

- Print a human‑readable summary report to stdout after processing completes.
- The report must include:
  - Total number of assets processed.
  - Total number of events processed (valid + invalid).
  - Number of invalid events skipped.
  - Top‑10 assets ranked by `total_usage_count`.
  - Top‑10 assets ranked by `unique_user_count`.

---

## 6. Architecture & Module Structure

Recommended module layout (not prescriptive, but encouraged):

```
asset_engagement/
    __init__.py          # Public API: calculate_engagement_scores()
    schema.py            # Pydantic models for input/output validation
    processor.py         # Core stream-processing logic
    reporter.py          # Stretch: business report formatter
```

### 6.1 Separation of Concerns

| Module         | Responsibility                                      |
| -------------- | --------------------------------------------------- |
| `schema.py`    | Define Pydantic models. Validate raw event dicts.   |
| `processor.py` | Stream ingestion, window filtering, metric aggregation. |
| `reporter.py`  | Format and print business reports.                  |
| `__init__.py`  | Wire components together. Expose the public API.    |

---

## 7. Production Readiness

### 7.1 Unit Tests

Cover each component in isolation:

- **Schema validation** — valid events pass; invalid events are rejected for each failure mode (missing field, empty string, bad datetime).
- **Processor** — correct metric aggregation, 3‑month window cutoff, handling of duplicate users (counted once), handling of assets from multiple creators.
- **Reporter** — report formatting, ranking correctness, edge cases (zero assets, zero events).

### 7.2 Integration Tests

- End‑to‑end test: feed a known stream of events into `calculate_engagement_scores()` and assert the exact output dictionary.
- Test with events that span the 3‑month boundary to verify window logic.
- Test with a mix of valid and invalid events to verify error resilience.

### 7.3 Logging

Use Python's standard `logging` module throughout:

| Level   | Usage                                                       |
| ------- | ----------------------------------------------------------- |
| `INFO`  | System transitions: processing started, processing complete, report generated. |
| `WARNING` | Invalid events skipped (include event summary + reason).  |
| `DEBUG` | Per‑event processing details (only when needed for debugging). |

Do **not** log at `ERROR` level for invalid input events — invalid data is expected in a raw stream and is handled gracefully.

---

## 8. Technical Guardrails

### 8.1 Allowed Dependencies

| Dependency | Purpose                          |
| ---------- | -------------------------------- |
| `pydantic` | Input schema validation.         |
| `pytest`   | Unit and integration testing.   |

No other third‑party dependencies without explicit approval. Use only the Python standard library for all other functionality (stream processing, logging, reporting, datetime handling).

### 8.2 Code Quality

- Type hints on all public functions and methods.
- Docstrings (Google or NumPy style) on all public APIs.
- Constants for magic numbers (e.g., `TRACKING_WINDOW_MONTHS = 3`).
- Follow PEP 8.

---

## 10. Out of Scope (Explicit)

- Persistence or database storage — this module is an in‑memory calculator.
- Authentication / authorization of event sources.
- Actual integration with the live Canva event pipeline.
- Real‑time dashboard or API endpoints — output is a Python dictionary (and optionally a printed report).
