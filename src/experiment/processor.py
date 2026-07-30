from datetime import datetime, timedelta

from src.experiment.event import Event


class Processor:
    """Analyzes a batch of exposure events for experiment integrity."""

    def __init__(self, window_months: int = 3) -> None:
        self._window_days = timedelta(days=window_months * 30)
        self._starts: dict[str, datetime] = {}
        self._groups: dict[tuple[str, str], dict[str, int]] = {}

    # -- public API ----------------------------------------------------------

    def process(self, events: list[Event]) -> list[dict]:
        """Compute integrity results from a batch of exposure events."""

        if not events:
            return []

        for ev in events:
            self._record_start(ev)
            if not self._is_within_window(ev):
                continue
            self._tally_variant(ev)

        return self._build_results()

    # -- private helpers ------------------------------------------------------

    def _record_start(self, event: Event) -> None:
        """Record the first-seen timestamp as the experiment start."""
        if event.experiment_id not in self._starts:
            self._starts[event.experiment_id] = event.parsed_timestamp

    def _is_within_window(self, event: Event) -> bool:
        """Return True if *event* falls within its experiment's window."""
        window_end = self._starts[event.experiment_id] + self._window_days
        return event.parsed_timestamp <= window_end

    def _tally_variant(self, event: Event) -> None:
        """Increment the variant count for a (user, experiment) pair."""
        key = (event.user_id, event.experiment_id)
        variant_counts = self._groups.setdefault(key, {})
        variant_counts[event.variant_id] = (
            variant_counts.get(event.variant_id, 0) + 1
        )

    def _build_results(self) -> list[dict]:
        """Convert variant counts into percentage-based integrity dicts."""
        results: list[dict] = []
        for (user_id, experiment_id), variant_counts in self._groups.items():
            total = sum(variant_counts.values())
            integrity = {
                variant: round(count / total, 4)
                for variant, count in variant_counts.items()
            }
            results.append(
                {
                    "user_id": user_id,
                    "experiment_id": experiment_id,
                    "experiment_integrity": integrity,
                }
            )
        return results
