"""Lightweight runtime drift detection.

Provider model aliases (e.g. "gpt-6-luna") can silently start pointing at a newer
snapshot, which can change answers. The API reports the exact model that served
each request, so we track the distinct values seen and warn loudly when a new one
appears. For deeper checks, run the golden-set suite (scripts/run_evals.py).
"""
import logging
import threading

logger = logging.getLogger(__name__)


class ModelDriftMonitor:
    def __init__(self) -> None:
        self._seen: dict[str, int] = {}
        self._lock = threading.Lock()

    def observe(self, model: str) -> None:
        with self._lock:
            previous = sorted(self._seen)
            is_new = model not in self._seen
            self._seen[model] = self._seen.get(model, 0) + 1
        if is_new and previous:
            logger.warning(
                "DRIFT WARNING: serving model changed to %r (previously seen: %s). "
                "Re-run `python -m scripts.run_evals` to check answer quality.",
                model,
                previous,
            )

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._seen)
