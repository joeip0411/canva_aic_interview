# Problem statement

Canva wants to understand how people are using its product based on user activity data.

Clarification
- Event stream data
- The stream is unbounded
- The events are mostly in order but sometimes there can be late arriving events
- Calculate event counts for each product for each day
- A daily window will be opened for 48 hours to allow late arriving events to be captured. Once past, not further events can go into the calculation. E.g. All events for 08/08/2026 can come into the window until 23:59:59 10/08/2026. Use the latest event timestamp to determine if a window should be closed. The events are expected to come in continuouosly.
- if an event fails schema validation, it should not be considered

Data schema
- Input schema
    - {user_id: str, product_id:str, event_timestamp:str, event_type:str}
- Output schema
    - {product_id(str) : {date(str) : event_count(int)}}

# Scope
- Core goal
    - Schema validation
    - EVent processing to calculate the summary stats
- Stretch goal
    - State persistence

# Production readiness
- unit test and integration test implemented
- Logging for meaningful metrics and system state transition

# Technical guardrail
- Use pydantic for schema validation, pytest for testing, and std library for everything else.







