from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from apps.market_data.services.providers.base import (
    ProviderFatal,
    ProviderHealth,
    ProviderNoData,
    ProviderRateLimited,
    ProviderTransient,
    Quote,
)

logger = logging.getLogger(__name__)


def _wrap_info_error(symbol: str, exc: Exception) -> Exception:
    """Translate a raw yfinance/requests exception into the provider taxonomy."""
    message = str(exc)
    lowered = message.lower()
    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return ProviderRateLimited(f"{symbol}: rate limited ({exc})")
    if "timeout" in lowered or "timed out" in lowered:
        return ProviderTransient(f"{symbol}: timeout ({exc})")
    if any(code in lowered for code in ("500", "502", "503", "504")):
        return ProviderTransient(f"{symbol}: server error ({exc})")
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        return exc
    return ProviderFatal(f"{symbol}: {exc}")


class YFinanceProvider:
    name = "yfinance"

    @staticmethod
    def to_provider_symbol(nse_code: str, exchange: str = "NSE") -> str:
        symbol = nse_code.strip().upper()
        if exchange == "BSE":
            return f"{symbol}.BO"
        return f"{symbol}.NS"

    def get_daily_candles(
        self,
        symbols: list[str],
        start: date,
        end: date,
    ) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}

        download_end = end + timedelta(days=1)
        downloaded = yf.download(
            tickers=symbols,
            start=start.isoformat(),
            end=download_end.isoformat(),
            interval="1d",
            auto_adjust=False,
            group_by="ticker",
            progress=False,
            threads=False,
        )

        if downloaded.empty:
            return {symbol: pd.DataFrame() for symbol in symbols}

        result: dict[str, pd.DataFrame] = {}
        if len(symbols) == 1:
            symbol = symbols[0]
            result[symbol] = self._normalize_frame(downloaded)
            return result

        for symbol in symbols:
            if symbol not in downloaded:
                result[symbol] = pd.DataFrame()
                continue
            result[symbol] = self._normalize_frame(downloaded[symbol])
        return result

    @staticmethod
    def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame

        # yfinance with group_by="ticker" returns MultiIndex columns like
        # ('RELIANCE.NS', 'Open'). Flatten to a single level so renaming works.
        if isinstance(frame.columns, pd.MultiIndex):
            frame = frame.copy()
            frame.columns = [col[1] if isinstance(col, tuple) else col for col in frame.columns]

        normalized = frame.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        for column in ["open", "high", "low", "close", "volume"]:
            if column not in normalized.columns:
                normalized[column] = pd.NA
        if "adj_close" not in normalized.columns:
            normalized["adj_close"] = pd.NA

        return normalized[["open", "high", "low", "close", "adj_close", "volume"]]

    def get_company_info(self, symbol: str) -> dict:
        try:
            info = yf.Ticker(symbol).info
        except Exception as exc:  # noqa: BLE001 - translated into the provider taxonomy
            wrapped = _wrap_info_error(symbol, exc)
            logger.warning("yfinance info fetch failed for %s: %s", symbol, wrapped)
            raise wrapped from exc

        if not info:
            raise ProviderNoData(f"{symbol}: empty company info")
        return info

    def get_live_quote(self, symbols: list[str]) -> dict[str, Quote]:
        """Fetch the latest quote for each symbol from the provider (cache-first lives above)."""
        result: dict[str, Quote] = {}
        for symbol in symbols:
            provider_symbol = self.to_provider_symbol(symbol)
            try:
                ticker = yf.Ticker(provider_symbol)
                hist = ticker.history(period="1d", interval="1m", auto_adjust=False)
            except Exception as exc:  # noqa: BLE001 - translate into provider taxonomy
                wrapped = _wrap_info_error(symbol, exc)
                logger.warning("yfinance live quote failed for %s: %s", symbol, wrapped)
                raise wrapped from exc
            if hist.empty:
                raise ProviderNoData(f"{symbol}: no live quote available")
            last = hist.iloc[-1]
            as_of = hist.index[-1]
            if hasattr(as_of, "to_pydatetime"):
                as_of = as_of.to_pydatetime()
            result[symbol] = Quote(symbol=symbol, price=float(last["Close"]), as_of=as_of)
        return result

    def get_intraday(self, symbol: str, interval: str = "5m") -> pd.DataFrame:
        """Intraday bars for *symbol* at *interval* (provider timestamps preserved)."""
        provider_symbol = self.to_provider_symbol(symbol)
        try:
            ticker = yf.Ticker(provider_symbol)
            hist = ticker.history(period="1d", interval=interval, auto_adjust=False)
        except Exception as exc:  # noqa: BLE001 - translate into provider taxonomy
            wrapped = _wrap_info_error(symbol, exc)
            logger.warning("yfinance intraday failed for %s: %s", symbol, wrapped)
            raise wrapped from exc
        if hist.empty:
            return pd.DataFrame()
        normalized = hist.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        for column in ["open", "high", "low", "close", "volume"]:
            if column not in normalized.columns:
                normalized[column] = pd.NA
        return normalized[["open", "high", "low", "close", "volume"]]

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=True, message="provider mapping available")
