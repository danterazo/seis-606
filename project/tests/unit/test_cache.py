from datetime import UTC, datetime

import pytest
from homelab_dashboard.models import ClusterSnapshot
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.cache import CachedStatusSource


class FakeClock:
    def __init__(self) -> None:
        self.now: float = 0.0

    def __call__(self) -> float:
        return self.now


class ScriptedSource:
    """Returns a numbered snapshot per call, or raises when told to."""

    def __init__(self) -> None:
        self.calls: int = 0
        self.fail: bool = False

    def fetch(self) -> ClusterSnapshot:
        self.calls += 1
        if self.fail:
            raise StatusSourceError("down")
        return ClusterSnapshot(source=f"call-{self.calls}", fetched_at=datetime(2026, 10, 7, tzinfo=UTC), nodes=())


def make_cache(*, source: ScriptedSource, clock: FakeClock, ttl: float = 4.0) -> CachedStatusSource:
    return CachedStatusSource(inner=source, ttl_seconds=ttl, clock=clock)


def test_repeated_fetches_within_the_ttl_share_one_query() -> None:
    source, clock = ScriptedSource(), FakeClock()
    cache = make_cache(source=source, clock=clock)

    results: list[str] = [cache.fetch().source for _ in range(3)]
    clock.now = 3.9
    results.append(cache.fetch().source)

    assert source.calls == 1
    assert set(results) == {"call-1"}


def test_a_new_query_is_made_once_the_ttl_has_passed() -> None:
    source, clock = ScriptedSource(), FakeClock()
    cache = make_cache(source=source, clock=clock)

    cache.fetch()
    clock.now = 4.0

    assert cache.fetch().source == "call-2"


def test_fetch_fresh_ignores_the_cache() -> None:
    source, clock = ScriptedSource(), FakeClock()
    cache = make_cache(source=source, clock=clock)

    cache.fetch()

    assert cache.fetch_fresh().source == "call-2"
    assert cache.fetch().source == "call-2"


def test_failures_are_cached_so_a_down_node_is_not_retried_per_request() -> None:
    source, clock = ScriptedSource(), FakeClock()
    source.fail = True
    cache = make_cache(source=source, clock=clock)

    for _ in range(3):
        with pytest.raises(StatusSourceError, match="down"):
            cache.fetch()

    assert source.calls == 1


def test_recovery_is_picked_up_after_the_ttl() -> None:
    source, clock = ScriptedSource(), FakeClock()
    source.fail = True
    cache = make_cache(source=source, clock=clock)
    with pytest.raises(StatusSourceError):
        cache.fetch()

    source.fail = False
    clock.now = 5.0
    recovered = cache.fetch()

    assert recovered.source == "call-2"
