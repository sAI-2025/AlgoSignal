from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

import pandas as pd


class ProviderError(Exception):
    """Base class for every provider failure.

    Callers branch on the concrete subclass to decide whether to retry, back off,
    record-and-continue, or abort (see ARCHITECTURE §7.1 / §8.4).
    """


class ProviderRateLimited(ProviderError):
    """The provider asked us to slow down (typically HTTP 429)."""


class ProviderNoData(ProviderError):
    """The provider returned no data (empty frame, delisted or unknown symbol)."""


class ProviderTransient(ProviderError):
    """A temporary failure such as a timeout or a 5xx response."""


class ProviderFatal(ProviderError):
    """A configuration or authentication failure that retrying cannot fix."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    as_of: datetime


@dataclass(frozen=True)
class ProviderHealth:
    ok: bool
    message: str = ""


class MarketDataProvider(Protocol):
    name: str

    def get_daily_candles(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]: ...

    def get_company_info(self, symbol: str) -> dict: ...

    def get_live_quote(self, symbols: list[str]) -> dict[str, Quote]: ...

    def get_intraday(self, symbol: str, interval: str = "5m") -> pd.DataFrame: ...

    def health_check(self) -> ProviderHealth: ...
