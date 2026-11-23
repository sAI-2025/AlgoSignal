from __future__ import annotations

import json

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.fetcher.services.scheduler import run_due_schedules


class Command(BaseCommand):
    help = "Run any due fetch jobs once (invoked by OS cron every ~10 minutes)"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Seed default schedules and report due jobs without executing them",
        )

    def handle(self, *args, **options) -> None:
        if options["dry_run"]:
            from apps.fetcher.services.scheduler import ensure_default_schedules, is_due

            ensure_default_schedules()
            now = timezone.now()
            from apps.fetcher.models import FetchSchedule

            due = [s.job_type for s in FetchSchedule.objects.all() if is_due(s, now=now)]
            self.stdout.write(json.dumps({"dry_run": True, "due": due}, indent=2))
            return

        runs = run_due_schedules(trigger="CLI")
        cache.set("scheduler:last_tick", timezone.now(), 3600)
        payload = [
            {
                "job_type": run.job_type,
                "status": run.status,
                "total": run.total_items,
                "success": run.success_items,
                "failed": run.failed_items,
                "rows_written": run.rows_written,
            }
            for run in runs
        ]
        self.stdout.write(json.dumps({"runs": payload}, indent=2))
