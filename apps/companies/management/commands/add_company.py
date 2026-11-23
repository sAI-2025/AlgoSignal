"""Add a single company/stock to the universe (CLI).

Usage:
  python manage.py add_company --nse-code RELIANCE --name "Reliance Industries" --sector "Energy"
  python manage.py add_company --nse-code TCS --name "Tata Consultancy Services" --sector "IT"
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company


class Command(BaseCommand):
    help = "Add a single company/stock to the tracked universe."

    def add_arguments(self, parser):
        parser.add_argument("--nse-code", required=True, help="NSE symbol (e.g. RELIANCE)")
        parser.add_argument("--name", required=True, help="Company name")
        parser.add_argument("--sector", default="", help="Sector (optional)")
        parser.add_argument("--industry", default="", help="Industry (optional)")
        parser.add_argument(
            "--bse-code", default="", help="BSE security code (optional)"
        )
        parser.add_argument(
            "--isin", default="", help="ISIN code (optional)"
        )

    def handle(self, *args, **options):
        nse_code = options["nse_code"].strip().upper()
        name = options["name"].strip()
        sector = options["sector"].strip() or None
        industry = options["industry"].strip() or None
        bse_code = options["bse_code"].strip() or None
        isin = options["isin"].strip() or None

        if not nse_code:
            raise CommandError("--nse-code is required.")
        if not name:
            raise CommandError("--name is required.")

        company, created = Company.objects.update_or_create(
            nse_code=nse_code,
            defaults={
                "company_name": name,
                "sector": sector,
                "industry": industry,
                "bse_code": bse_code,
                "isin": isin,
                "is_active": True,
            },
        )
        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(f"Company {action}: {nse_code} — {name}")
        )
