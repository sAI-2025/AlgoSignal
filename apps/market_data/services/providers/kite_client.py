from __future__ import annotations

from datetime import date

import pandas as pd

from apps.market_data.services.providers.base import ProviderHealth, Quote


class KiteClient:
    name = "kite"

    def get_daily_candles(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]:
        raise NotImplementedError("Kite adapter will be implemented in a later phase")

    def get_company_info(self, symbol: str) -> dict:
        raise NotImplementedError("Kite adapter will be implemented in a later phase")

    def get_live_quote(self, symbols: list[str]) -> dict[str, Quote]:
        raise NotImplementedError("Kite adapter will be implemented in a later phase")

    def get_intraday(self, symbol: str, interval: str = "5m") -> pd.DataFrame:
        raise NotImplementedError("Kite adapter will be implemented in a later phase")

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=False, message="kite adapter not configured")
