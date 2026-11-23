"""Retry with back-off for provider calls (ARCHITECTURE §8.4).

The provider layer raises the typed errors from
``market_data.services.providers.base``. This helper retries transient failures with a
short back-off and rate-limit failures with a longer back-off, but never retries
``ProviderNoData`` (record, don't retry) or ``ProviderFatal`` (re-raise immediately).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from apps.market_data.services.providers.base import (
    ProviderFatal,
    ProviderNoData,
    ProviderRateLimited,
    ProviderTransient,
)

logger = logging.getLogger(__name__)

DEFAULT_TRANSIENT_DELAYS: tuple[int, ...] = (5, 15, 45)
DEFAULT_RATE_LIMIT_DELAYS: tuple[int, ...] = (30, 60, 120)


def call_with_retry[T](
    func: Callable[[], T],
    *,
    retries: int = 3,
    transient_delays: tuple[int, ...] = DEFAULT_TRANSIENT_DELAYS,
    rate_limit_delays: tuple[int, ...] = DEFAULT_RATE_LIMIT_DELAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``func`` retrying transient / rate-limited failures with back-off.

    ``sleep`` is injectable so tests run instantly without real delays. The last
    exception is re-raised once retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            return func()
        except ProviderNoData:
            # Deterministic: no point retrying.
            raise
        except ProviderFatal:
            # Configuration / auth problem: retrying cannot help.
            raise
        except ProviderRateLimited as exc:
            last_exc = exc
            if attempt < retries - 1:
                delay = rate_limit_delays[min(attempt, len(rate_limit_delays) - 1)]
                logger.warning(
                    "Provider rate-limited (attempt %s/%s); back-off %ss",
                    attempt + 1,
                    retries,
                    delay,
                )
                sleep(delay)
        except ProviderTransient as exc:
            last_exc = exc
            if attempt < retries - 1:
                delay = transient_delays[min(attempt, len(transient_delays) - 1)]
                logger.warning(
                    "Provider transient error (attempt %s/%s); back-off %ss",
                    attempt + 1,
                    retries,
                    delay,
                )
                sleep(delay)

    assert last_exc is not None  # noqa: S101 - for type narrowing only
    raise last_exc
