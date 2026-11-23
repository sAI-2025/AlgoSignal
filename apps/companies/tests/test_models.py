import datetime as dt

import pytest
from django.db import IntegrityError

from apps.companies.models import Company, CompanyProfile, IndexMembership


@pytest.mark.django_db
def test_company_requires_unique_nse_code() -> None:
    Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE")

    with pytest.raises(IntegrityError):
        Company.objects.create(company_name="Another Reliance", nse_code="RELIANCE")


@pytest.mark.django_db
def test_index_membership_allows_only_one_active_membership_per_index() -> None:
    company = Company.objects.create(company_name="Infosys", nse_code="INFY")

    IndexMembership.objects.create(
        company=company,
        index_code="NIFTY100",
        effective_from=dt.date(2026, 1, 1),
        effective_to=None,
    )

    with pytest.raises(IntegrityError):
        IndexMembership.objects.create(
            company=company,
            index_code="NIFTY100",
            effective_from=dt.date(2026, 2, 1),
            effective_to=None,
        )


@pytest.mark.django_db
def test_company_profile_is_one_to_one() -> None:
    company = Company.objects.create(company_name="TCS", nse_code="TCS")
    CompanyProfile.objects.create(company=company, source_name="Annual Report")

    with pytest.raises(IntegrityError):
        CompanyProfile.objects.create(company=company, source_name="Website")
