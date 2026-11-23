import datetime as dt

import pytest

from apps.companies.models import Company, IndexMembership
from apps.companies.services.importer import import_constituents_from_csv_text


@pytest.mark.django_db
def test_importer_handles_renamed_columns() -> None:
    csv_text = "\n".join(
        [
            "Name,NSE Symbol,Industry,ISIN Code",
            "Reliance Industries,RELIANCE,Oil & Gas,INE002A01018",
            "Infosys,INFY,IT,INE009A01021",
        ]
    )

    summary = import_constituents_from_csv_text(
        csv_text,
        index_code="NIFTY100",
        source_url="https://example.com/nifty100.csv",
        as_of=dt.date(2026, 11, 23),
    )

    assert summary.processed_rows == 2
    assert summary.added_companies == 2
    assert Company.objects.filter(nse_code="RELIANCE", sector="Oil & Gas").exists()
    assert Company.objects.filter(nse_code="INFY", isin="INE009A01021").exists()


@pytest.mark.django_db
def test_importer_skips_bad_rows_but_continues() -> None:
    csv_text = "\n".join(
        [
            "Company Name,Symbol,Industry",
            "Good Company,GOOD,Finance",
            "Missing Symbol,,IT",
            ",NONAME,Energy",
        ]
    )

    summary = import_constituents_from_csv_text(
        csv_text,
        index_code="NIFTY100",
        source_url="https://example.com/nifty100.csv",
        as_of=dt.date(2026, 11, 23),
    )

    assert summary.processed_rows == 1
    assert summary.skipped_rows == 2
    assert len(summary.errors) == 2
    assert Company.objects.filter(nse_code="GOOD").exists()


@pytest.mark.django_db
def test_importer_is_idempotent_for_same_csv_hash() -> None:
    csv_text = """Company Name,Symbol,Industry\nTata Consultancy Services,TCS,IT\n"""

    first = import_constituents_from_csv_text(
        csv_text,
        index_code="NIFTY100",
        source_url="https://example.com/nifty100.csv",
        as_of=dt.date(2026, 11, 23),
    )
    second = import_constituents_from_csv_text(
        csv_text,
        index_code="NIFTY100",
        source_url="https://example.com/nifty100.csv",
        as_of=dt.date(2026, 11, 24),
    )

    assert first.skipped_unchanged is False
    assert second.skipped_unchanged is True
    assert Company.objects.filter(nse_code="TCS").count() == 1
    assert IndexMembership.objects.filter(index_code="NIFTY100").count() == 1
