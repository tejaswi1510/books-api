"""Rate limiting.

RateLimiter is an interface so the in-memory implementation can later be swapped
for a shared store (e.g. Redis) without touching the API layer.

InMemoryRateLimiter uses a *sliding window log*: it remembers the timestamp of each
recent request per key and allows a new one only if fewer than `limit` happened in
the last `window_seconds`. It is accurate (no burst at window boundaries) and cheap
for small limits. LIMITATION: state lives in this process only, so with several
uvicorn workers/servers each one enforces its own limit. Use Redis for that case.
"""
import math
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # whole seconds until a slot frees up (0 when allowed)


class RateLimiter(ABC):
    @abstractmethod
    def hit(self, key: str) -> RateLimitResult:
        """Record one request for `key` and say whether it is allowed."""


class InMemoryRateLimiter(RateLimiter):
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock  # injectable so tests can control time
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_prune = clock()

    def hit(self, key: str) -> RateLimitResult:
        now = self._clock()
        with self._lock:
            self._prune(now)
            queue = self._hits.setdefault(key, deque())
            cutoff = now - self._window
            while queue and queue[0] <= cutoff:
                queue.popleft()

            if len(queue) >= self._limit:
                retry_after = max(1, math.ceil(queue[0] + self._window - now))
                return RateLimitResult(False, self._limit, 0, retry_after)

            queue.append(now)
            return RateLimitResult(True, self._limit, self._limit - len(queue), 0)

    def _prune(self, now: float) -> None:
        """Occasionally drop keys with no recent activity so memory can't grow forever."""
        if now - self._last_prune < self._window:
            return
        self._last_prune = now
        cutoff = now - self._window
        stale = [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]
        for k in stale:
            del self._hits[k]
