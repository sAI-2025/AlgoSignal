import pytest

from apps.companies.models import Company
from apps.market_data.models import Instrument
from apps.market_data.services.instrument_mapper import (
    map_active_companies,
    map_company_to_instrument,
)
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider


def test_yfinance_symbol_mapper_handles_special_nse_symbols() -> None:
    provider = YFinanceProvider()

    assert provider.to_provider_symbol("M&M") == "M&M.NS"
    assert provider.to_provider_symbol("BAJAJ-AUTO") == "BAJAJ-AUTO.NS"


@pytest.mark.django_db
def test_map_company_to_instrument_prefers_exchange_code() -> None:
    company = Company.objects.create(
        company_name="Bajaj Auto",
        nse_code="BAJAJ-AUTO",
        bse_code="532977",
    )

    assert map_company_to_instrument(company, exchange=Instrument.Exchange.NSE) == "BAJAJ-AUTO"
    assert map_company_to_instrument(company, exchange=Instrument.Exchange.BSE) == "532977"


@pytest.mark.django_db
def test_map_instruments_upserts_without_duplicates() -> None:
    Company.objects.create(company_name="Mahindra & Mahindra", nse_code="M&M", is_active=True)
    Company.objects.create(company_name="Bajaj Auto", nse_code="BAJAJ-AUTO", is_active=True)

    first = map_active_companies()
    second = map_active_companies()

    assert first.created == 2
    assert second.updated == 2
    assert Instrument.objects.filter(exchange=Instrument.Exchange.NSE).count() == 2
    assert Instrument.objects.filter(tradingsymbol="M&M", provider_symbol="M&M.NS").exists()
