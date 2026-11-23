from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.market_data.models import Instrument
from apps.market_data.services.instrument_mapper import map_active_companies


class Command(BaseCommand):
    help = "Map active companies to provider symbols and upsert instruments"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--exchange",
            default=Instrument.Exchange.NSE,
            choices=[Instrument.Exchange.NSE, Instrument.Exchange.BSE],
            help="Exchange to map symbols for",
        )

    def handle(self, *args, **options) -> None:
        exchange = options["exchange"]
        summary = map_active_companies(exchange=exchange)

        self.stdout.write(
            self.style.SUCCESS(
                f"Mapping complete for {exchange}: "
                f"created={summary.created}, updated={summary.updated}, skipped={summary.skipped}"
            )
        )
