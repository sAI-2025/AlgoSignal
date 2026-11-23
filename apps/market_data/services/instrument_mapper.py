from __future__ import annotations

from dataclasses import dataclass

from apps.companies.models import Company
from apps.market_data.models import Instrument
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider


@dataclass
class InstrumentMapSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0


def map_company_to_instrument(company: Company, exchange: str = Instrument.Exchange.NSE) -> str:
    if exchange == Instrument.Exchange.NSE:
        return company.nse_code
    if exchange == Instrument.Exchange.BSE and company.bse_code:
        return company.bse_code
    raise ValueError(f"Company {company.nse_code} does not have symbol for exchange {exchange}")


def map_active_companies(exchange: str = Instrument.Exchange.NSE) -> InstrumentMapSummary:
    summary = InstrumentMapSummary()
    provider = YFinanceProvider()

    active_companies = Company.objects.filter(is_active=True).order_by("id")
    for company in active_companies:
        try:
            tradingsymbol = map_company_to_instrument(company, exchange=exchange)
        except ValueError:
            summary.skipped += 1
            continue

        provider_symbol = provider.to_provider_symbol(company.nse_code, exchange=exchange)
        _, created = Instrument.objects.update_or_create(
            company=company,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            defaults={
                "provider_symbol": provider_symbol,
                "instrument_type": "EQ",
            },
        )

        if created:
            summary.created += 1
        else:
            summary.updated += 1

    return summary
