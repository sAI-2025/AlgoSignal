"""Cache-first live quotes + intraday (ARCHITECTURE §9, PRD FR-14).

Live data is *never* persisted (tier T5). Quotes are cached for 30 s, intraday for 60 s.
Outside market hours the endpoint returns the last completed close with
``market_state="CLOSED`` and the client stops polling.
"""

from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

from apps.companies.models import Company
from apps.core.market_hours import market_state
from apps.market_data.selectors import load_candles_dataframe
from apps.market_data.services.fundamentals import fetch_and_store_metrics
from apps.market_data.services.providers.base import ProviderError, ProviderNoData
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider

QUOTE_TTL = 30
INTRADAY_TTL = 60


def _quote_key(symbol: str) -> str:
    return f"live:quote:{symbol.upper()}"


def _intraday_key(symbol: str, interval: str) -> str:
    return f"live:intraday:{symbol.upper()}:{interval}"


def _previous_close(symbol: str) -> float | None:
    company = Company.objects.filter(nse_code__iexact=symbol).first()
    if company is None:
        return None
    metrics = getattr(company, "metrics", None)
    if metrics is not None and metrics.previous_close is not None:
        return float(metrics.previous_close)
    frame = load_candles_dataframe(company.id, limit=2)
    if len(frame.index) >= 2:
        return float(frame["close"].iloc[-2])
    return None


def _enrich(symbol: str, quote, *, now) -> dict:
    previous = _previous_close(symbol)
    price = quote.price
    payload: dict = {
        "symbol": symbol,
        "price": price,
        "as_of": quote.as_of.isoformat(),
        "market_state": market_state(now),
        "source": "yfinance",
        "delayed_hint": "Data may be delayed.",
    }
    if previous is not None and previous > 0:
        payload["change"] = price - previous
        payload["change_pct"] = (price - previous) / previous * 100
    return payload


def get_live_quote(symbol: str, *, provider=None, now=None) -> dict:
    """Return a single live quote, served from cache when fresh."""
    provider = provider or YFinanceProvider()
    now = now or timezone.now()
    key = _quote_key(symbol)

    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        quotes = provider.get_live_quote([symbol])
    except ProviderError:
        stale = cache.get(key)
        if stale is not None:
            return stale
        raise

    quote = quotes.get(symbol)
    if quote is None:
        raise ProviderNoData(f"{symbol}: no live quote available")

    payload = _enrich(symbol, quote, now=now)
    cache.set(key, payload, QUOTE_TTL)
    return payload


def get_live_quotes(symbols: list[str], *, provider=None, now=None) -> list[dict]:
    """Return live quotes for up to 20 symbols (batch)."""
    provider = provider or YFinanceProvider()
    now = now or timezone.now()
    symbols = [s.upper() for s in symbols][:20]
    if not symbols:
        return []

    cached_results: list[dict] = []
    uncached: list[str] = []
    for symbol in symbols:
        cached = cache.get(_quote_key(symbol))
        if cached is not None:
            cached_results.append(cached)
        else:
            uncached.append(symbol)

    if uncached:
        try:
            quotes = provider.get_live_quote(uncached)
        except ProviderError:
            # serve whatever stale we have for the failed symbols
            for symbol in uncached:
                stale = cache.get(_quote_key(symbol))
                if stale is not None:
                    cached_results.append(stale)
            return cached_results

        for symbol in uncached:
            quote = quotes.get(symbol)
            if quote is None:
                continue
            payload = _enrich(symbol, quote, now=now)
            cache.set(_quote_key(symbol), payload, QUOTE_TTL)
            cached_results.append(payload)

    return cached_results


def get_intraday(symbol: str, interval: str = "5m", *, provider=None) -> list[dict]:
    """Return intraday bars (list of OHLCV dicts) for *symbol*, cached 60 s."""
    provider = provider or YFinanceProvider()
    key = _intraday_key(symbol, interval)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        frame = provider.get_intraday(symbol, interval=interval)
    except ProviderError:
        stale = cache.get(key)
        if stale is not None:
            return stale
        raise

    if frame.empty:
        return []

    records = []
    for index, row in frame.iterrows():
        records.append(
            {
                "time": index.isoformat(),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": int(row["volume"]) if row["volume"] is not None else 0,
            }
        )
    cache.set(key, records, INTRADAY_TTL)
    return records


def refresh_metrics(symbol: str, *, provider=None) -> dict:
    """Live-fetch fresh fundamentals for *symbol* and upsert the snapshot (1/min)."""
    provider = provider or YFinanceProvider()
    company = Company.objects.filter(nse_code__iexact=symbol).first()
    if company is None:
        raise ProviderNoData(f"{symbol}: company not found")
    result = fetch_and_store_metrics(company, provider=provider)
    metrics = getattr(company, "metrics", None)
    if metrics is None:
        raise ProviderError(f"{symbol}: metrics could not be stored")
    return {
        "company_id": metrics.company_id,
        "current_price": float(metrics.current_price) if metrics.current_price else None,
        "previous_close": float(metrics.previous_close) if metrics.previous_close else None,
        "fetched_at": metrics.fetched_at.isoformat() if metrics.fetched_at else None,
        "missing_fields": result.missing_fields,
    }
