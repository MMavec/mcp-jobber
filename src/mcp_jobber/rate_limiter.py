"""Async token-bucket rate limiter sized for Jobber's 2500 req / 5 min policy."""

from __future__ import annotations

import asyncio
import time


class AsyncTokenBucket:
    """Leaky token bucket. Default capacity and refill match Jobber's window.

    `capacity` tokens refill linearly over `window_seconds`. `acquire()` blocks
    until a token is free, so callers never need to catch 429s for the baseline
    throughput; Jobber-side 429s still bubble up from the GraphQL client and
    signal that cost-based throttling (not request count) tripped.
    """

    def __init__(
        self,
        capacity: int = 2500,
        window_seconds: float = 300.0,
        *,
        monotonic=time.monotonic,
    ) -> None:
        if capacity <= 0 or window_seconds <= 0:
            raise ValueError("capacity and window_seconds must be positive")
        self.capacity = float(capacity)
        self.refill_per_sec = capacity / window_seconds
        self._tokens = float(capacity)
        self._updated = monotonic()
        self._lock = asyncio.Lock()
        self._monotonic = monotonic

    def _refill(self) -> None:
        now = self._monotonic()
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_sec)
            self._updated = now

    async def acquire(self, cost: float = 1.0) -> None:
        if cost <= 0:
            return
        if cost > self.capacity:
            raise ValueError(f"cost {cost} exceeds bucket capacity {self.capacity}")
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= cost:
                    self._tokens -= cost
                    return
                deficit = cost - self._tokens
                wait = deficit / self.refill_per_sec
            await asyncio.sleep(wait)

    @property
    def tokens(self) -> float:
        self._refill()
        return self._tokens
