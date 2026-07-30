# Problem Statement
Canva runs hundreds of experiments in parallel across our growth funnels. Sometimes users are exposed to conflicting variations, or their variant assignments drift over time due to cross-device sync issues. We have a massive raw event stream capturing every time a user is exposed to an experiment variation. We need you to build a Python module that analyzes a batch of these raw exposure logs to evaluate _Experiment Integrity_ and produce a clean, unpolluted dataset for our experimentation dashboard.

# Clarifications
- **Experiment Integrity**
    - Ensure a user was presented the same variant within each experiment throughout the entire experiment cycle.
- **Volume**
    - Data volume is huge — at Canva's scale.
- **Window of Analysis**
    - 3 months from experiment creation.
    - Events outside this window are not considered.

# Schema
- **Input**
    - `user_id: str`
    - `experiment_id: str`
    - `variant_id: str`
    - `timestamp: str`
    - `event_type: str`
- **Output**
    - `user_id: str`
    - `experiment_id: str`
    - `experiment_integrity: dict{variant_id: str, percentage: float}`

# Scope
- **Event class** — input schema validation.
- **Processor class** — takes Event instances as input and outputs a Python dictionary containing the result data.

# Production Readiness
- **Unit tests** for the Event class, covering both positive and negative cases.
- **Integration tests** for the Processor class, covering the happy path and scenarios that include both clean and polluted data.

# Technical Guardrails
- Use **Pydantic** for schema validation in the Event class.
- Use **pytest** for testing.
- Use the Python **standard library** for everything else.
