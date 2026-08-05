# Problem
We receive a stream of events from users interacting with our application.

We'd like a small service that processes these events and provides useful information to downstream systems.

Clarification
- The stream is unbounded
- The data is arrive roughly in order but can be out sometimes
- If an event has a timestamp that is at least 24 hours before the latest event time, discard that event
- Close the window for a particular day if the a new event received is at least 24 hours after the date.
- Report the number of events a user have on a particular day
- Goal
    To calculate how many interaction a user have on a particular day

# Schema
Input
    - user_id:str
    - event_type: str
    - event_timestamp:str
Output
    - {date : {user_id: count}}
    - date and user_id is string, and count is integer

# Scope
Core goals
    - Event schema validation
    - Event processing and outputing the metrics

Stretch goal
    - State persistence

# Production readiness
- Unit test and integration test implemented
- meaningful logging to show useful metrics and transition between system states

# Technical guardrails
- Use pydantic for schema validation and pytest for testing.
- Use Standard library for everything else.