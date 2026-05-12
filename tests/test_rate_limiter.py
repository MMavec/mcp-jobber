"""Unit tests for the async token-bucket rate limiter."""

from __future__ import annotations

import asyncio

import pytest

from mcp_jobber.rate_limiter import AsyncTokenBucket


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


async def test_rejects_bad_config():
    with pytest.raises(ValueError):
        AsyncTokenBucket(capacity=0)
    with pytest.raises(ValueError):
        AsyncTokenBucket(capacity=10, window_seconds=0)


async def test_initial_capacity_is_full():
    bucket = AsyncTokenBucket(capacity=3, window_seconds=60)
    # Three immediate acquires should not block.
    for _ in range(3):
        await asyncio.wait_for(bucket.acquire(), timeout=0.1)


async def test_blocks_when_empty_and_refills_over_time():
    clock = FakeClock()
    bucket = AsyncTokenBucket(capacity=2, window_seconds=4.0, monotonic=clock)
    await bucket.acquire()
    await bucket.acquire()
    assert bucket.tokens == pytest.approx(0.0, abs=1e-6)

    # Simulate 3 seconds of wall time: refill rate is 0.5 tok/s => +1.5 tokens.
    clock.advance(3.0)
    assert bucket.tokens == pytest.approx(1.5, abs=1e-6)


async def test_cost_greater_than_capacity_raises():
    bucket = AsyncTokenBucket(capacity=5, window_seconds=60)
    with pytest.raises(ValueError):
        await bucket.acquire(cost=6)


async def test_default_matches_jobber_window():
    bucket = AsyncTokenBucket()
    assert bucket.capacity == 2500
    assert bucket.refill_per_sec == pytest.approx(2500 / 300)
