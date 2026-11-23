from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.companies.services.importer import ImporterError, run_constituent_import


class Command(BaseCommand):
    help = "Import index constituents and update company/membership snapshots"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--index-code",
            default=settings.INDEX_UNIVERSE,
            help="Index code to import (default from INDEX_UNIVERSE)",
        )

    def handle(self, *args, **options) -> None:
        index_code = options["index_code"]

        try:
            summary = run_constituent_import(index_code=index_code)
        except ImporterError as exc:
            raise CommandError(str(exc)) from exc

        payload = {
            "index_code": summary.index_code,
            "source_url": summary.source_url,
            "source_sha256": summary.source_sha256,
            "total_rows": summary.total_rows,
            "processed_rows": summary.processed_rows,
            "added_companies": summary.added_companies,
            "updated_companies": summary.updated_companies,
            "skipped_rows": summary.skipped_rows,
            "closed_memberships": summary.closed_memberships,
            "skipped_unchanged": summary.skipped_unchanged,
            "errors": summary.errors,
        }
        self.stdout.write(json.dumps(payload, indent=2))

        if summary.skipped_rows > 0:
            self.stderr.write(
                self.style.WARNING(f"Import finished with {summary.skipped_rows} skipped rows.")
            )
