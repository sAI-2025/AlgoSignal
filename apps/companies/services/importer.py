from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import requests
from django.conf import settings
from django.db import transaction
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from apps.companies.models import Company, IndexMembership
from apps.companies.services.column_mapper import map_columns

logger = logging.getLogger(__name__)


@dataclass
class ImportSummary:
    index_code: str
    source_url: str
    source_sha256: str
    total_rows: int = 0
    processed_rows: int = 0
    added_companies: int = 0
    updated_companies: int = 0
    skipped_rows: int = 0
    closed_memberships: int = 0
    skipped_unchanged: bool = False
    errors: list[dict[str, str]] = field(default_factory=list)


class ImporterError(Exception):
    pass


def _build_http_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _csv_hash(csv_text: str) -> str:
    return hashlib.sha256(csv_text.encode("utf-8")).hexdigest()


def _latest_hash_for_index(index_code: str) -> str | None:
    latest = (
        IndexMembership.objects.filter(index_code=index_code)
        .order_by("-imported_at")
        .values_list("source_sha256", flat=True)
        .first()
    )
    return latest or None


def fetch_csv_from_config(index_code: str) -> tuple[str, str]:
    url_map = settings.NIFTY_INDEX_CSV_URLS
    urls = url_map.get(index_code, [])
    if not urls:
        raise ImporterError(f"No source URLs configured for {index_code}")

    session = _build_http_session()
    user_agent = getattr(
        settings,
        "NIFTY_IMPORT_USER_AGENT",
        "AlgoSignal/1.0 (constituent-import; +https://example.local)",
    )

    errors: list[str] = []
    for url in urls:
        try:
            response = session.get(url, timeout=20, headers={"User-Agent": user_agent})
            response.raise_for_status()
            return response.text, url
        except requests.RequestException as exc:
            errors.append(f"{url}: {exc}")

    raise ImporterError(f"Failed to fetch CSV for {index_code}. Errors: {' | '.join(errors)}")


def _sanitize(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _find_existing_company(isin: str, nse_code: str) -> Company | None:
    if isin:
        company = Company.objects.filter(isin=isin).first()
        if company:
            return company
    if nse_code:
        return Company.objects.filter(nse_code=nse_code).first()
    return None


def _close_removed_memberships(index_code: str, active_company_ids: set[int], as_of: date) -> int:
    current_memberships = IndexMembership.objects.select_related("company").filter(
        index_code=index_code,
        effective_to__isnull=True,
    )

    closed = 0
    for membership in current_memberships:
        if membership.company_id in active_company_ids:
            continue
        membership.effective_to = as_of
        membership.save(update_fields=["effective_to"])
        closed += 1

        has_other_active_membership = IndexMembership.objects.filter(
            company_id=membership.company_id,
            effective_to__isnull=True,
        ).exists()
        if not has_other_active_membership:
            Company.objects.filter(pk=membership.company_id).update(is_active=False)

    return closed


@transaction.atomic
def import_constituents_from_csv_text(
    csv_text: str,
    *,
    index_code: str,
    source_url: str,
    as_of: date | None = None,
) -> ImportSummary:
    as_of = as_of or date.today()
    source_sha256 = _csv_hash(csv_text)

    summary = ImportSummary(
        index_code=index_code,
        source_url=source_url,
        source_sha256=source_sha256,
    )

    if _latest_hash_for_index(index_code) == source_sha256:
        summary.skipped_unchanged = True
        logger.info("Constituent import skipped (unchanged)", extra={"index_code": index_code})
        return summary

    frame = pd.read_csv(io.StringIO(csv_text))
    mapped = map_columns(frame)
    if mapped.missing_required:
        raise ImporterError(f"CSV missing required columns: {', '.join(mapped.missing_required)}")

    normalized = mapped.frame
    summary.total_rows = int(len(normalized.index))

    active_company_ids: set[int] = set()

    for _, row in normalized.iterrows():
        company_name = _sanitize(row.get("company_name"))
        nse_code = _sanitize(row.get("nse_code")).upper()
        isin = _sanitize(row.get("isin")).upper()
        sector = _sanitize(row.get("sector"))

        if not company_name or not nse_code:
            summary.skipped_rows += 1
            summary.errors.append(
                {
                    "symbol": nse_code or "",
                    "error_code": "INVALID_ROW",
                    "message": "Required fields company_name and nse_code are missing",
                }
            )
            continue

        company = _find_existing_company(isin=isin, nse_code=nse_code)
        if company is None:
            company = Company.objects.create(
                company_name=company_name,
                nse_code=nse_code,
                isin=isin or None,
                sector=sector or None,
                is_active=True,
            )
            summary.added_companies += 1
        else:
            changed = False
            if company.company_name != company_name:
                company.company_name = company_name
                changed = True
            if company.nse_code != nse_code:
                company.nse_code = nse_code
                changed = True
            if isin and company.isin != isin:
                company.isin = isin
                changed = True
            if sector and company.sector != sector:
                company.sector = sector
                changed = True
            if not company.is_active:
                company.is_active = True
                changed = True

            if changed:
                company.save()
                summary.updated_companies += 1

        active_company_ids.add(company.id)

        IndexMembership.objects.get_or_create(
            company=company,
            index_code=index_code,
            effective_from=as_of,
            defaults={
                "effective_to": None,
                "source_url": source_url,
                "source_sha256": source_sha256,
            },
        )

        IndexMembership.objects.filter(
            company=company,
            index_code=index_code,
            effective_to__isnull=True,
        ).exclude(effective_from=as_of).update(effective_to=as_of)

        summary.processed_rows += 1

    summary.closed_memberships = _close_removed_memberships(
        index_code=index_code,
        active_company_ids=active_company_ids,
        as_of=as_of,
    )

    logger.info(
        "Constituent import completed",
        extra={
            "index_code": index_code,
            "processed_rows": summary.processed_rows,
            "added": summary.added_companies,
            "updated": summary.updated_companies,
            "skipped_rows": summary.skipped_rows,
            "closed_memberships": summary.closed_memberships,
        },
    )

    return summary


def run_constituent_import(index_code: str) -> ImportSummary:
    csv_text, source_url = fetch_csv_from_config(index_code)
    return import_constituents_from_csv_text(
        csv_text,
        index_code=index_code,
        source_url=source_url,
    )
