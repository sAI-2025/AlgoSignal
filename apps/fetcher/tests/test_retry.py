from __future__ import annotations

import pytest

from apps.fetcher.services.retry import call_with_retry
from apps.market_data.services.providers.base import (
    ProviderFatal,
    ProviderNoData,
    ProviderRateLimited,
    ProviderTransient,
)


def test_returns_on_first_success() -> None:
    assert call_with_retry(lambda: 42) == 42


def test_retries_transient_then_succeeds() -> None:
    calls = {"n": 0}
    slept: list[float] = []

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise ProviderTransient("timeout")
        return "ok"

    result = call_with_retry(flaky, retries=3, sleep=slept.append)

    assert result == "ok"
    assert calls["n"] == 2
    assert slept == [5]  # first transient delay


def test_rate_limited_uses_longer_backoff() -> None:
    slept: list[float] = []

    def always_limited() -> None:
        raise ProviderRateLimited("429")

    with pytest.raises(ProviderRateLimited):
        call_with_retry(always_limited, retries=3, sleep=slept.append)

    assert slept == [30, 60]  # rate-limit delays for attempts 1 and 2


def test_no_data_not_retried() -> None:
    calls = {"n": 0}

    def no_data() -> None:
        calls["n"] += 1
        raise ProviderNoData("empty")

    with pytest.raises(ProviderNoData):
        call_with_retry(no_data, retries=3, sleep=lambda _s: None)

    assert calls["n"] == 1


def test_fatal_not_retried() -> None:
    calls = {"n": 0}

    def fatal() -> None:
        calls["n"] += 1
        raise ProviderFatal("auth")

    with pytest.raises(ProviderFatal):
        call_with_retry(fatal, retries=3, sleep=lambda _s: None)

    assert calls["n"] == 1


def test_exhausts_retries_and_raises_last() -> None:
    calls = {"n": 0}

    def always_transient() -> None:
        calls["n"] += 1
        raise ProviderTransient(f"boom {calls['n']}")

    with pytest.raises(ProviderTransient, match="boom 3"):
        call_with_retry(always_transient, retries=3, sleep=lambda _s: None)

    assert calls["n"] == 3
