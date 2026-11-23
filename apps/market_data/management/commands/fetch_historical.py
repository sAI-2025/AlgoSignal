from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from apps.market_data.models import Instrument
from apps.market_data.services.historical_data import backfill_company_history


class Command(BaseCommand):
    help = "Fetch and store historical OHLCV candles for mapped instruments"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--years", type=int, default=3, help="Backfill years when no history exists"
        )
        parser.add_argument("--symbol", type=str, default="", help="Optional NSE symbol filter")
        parser.add_argument("--start", type=str, default="", help="Optional start date YYYY-MM-DD")
        parser.add_argument("--end", type=str, default="", help="Optional end date YYYY-MM-DD")

    def handle(self, *args, **options) -> None:
        years = options["years"]
        symbol = options["symbol"].strip().upper()
        start = date.fromisoformat(options["start"]) if options["start"] else None
        end = date.fromisoformat(options["end"]) if options["end"] else None

        instruments = Instrument.objects.select_related("company").filter(
            exchange=Instrument.Exchange.NSE
        )
        if symbol:
            instruments = instruments.filter(company__nse_code=symbol)

        total_written = 0
        total_skipped = 0
        for instrument in instruments.order_by("company__nse_code"):
            result = backfill_company_history(
                instrument,
                years=years,
                start=start,
                end=end,
            )
            total_written += result.written_rows
            total_skipped += result.skipped_incomplete_rows
            self.stdout.write(
                f"{instrument.company.nse_code}: written={result.written_rows}, "
                f"skipped_incomplete={result.skipped_incomplete_rows}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Historical fetch completed: written={total_written}, "
                f"skipped_incomplete={total_skipped}"
            )
        )
