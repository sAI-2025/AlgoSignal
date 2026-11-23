"""Create or update the login user (single superuser per PRD D10).

Idempotent: run it again to rotate the password or change staff status. The default
username/password (``sai`` / ``1234``) are local-dev conveniences — override them and
pick a strong password in production.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the login user (superuser by default)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="sai", help="Username (default: sai).")
        parser.add_argument("--password", default="1234", help="Password (default: 1234).")
        parser.add_argument("--email", default="", help="Optional email address.")
        parser.add_argument(
            "--no-staff",
            action="store_true",
            help="Create a regular user instead of a staff superuser.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options["username"]
        password = options["password"]
        is_privileged = not options["no_staff"]

        user = user_model.objects.filter(username=username).first()
        created = user is None
        if created:
            user = user_model(username=username)

        user.email = options["email"]
        user.is_staff = is_privileged
        user.is_superuser = is_privileged
        user.set_password(password)
        user.save()

        if len(password) < 8:
            self.stderr.write(
                self.style.WARNING(
                    f"Password for '{username}' is shorter than 8 characters - fine for local "
                    "development, but use a strong password in production."
                )
            )

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} user '{username}' (staff={user.is_staff}, superuser={user.is_superuser})."
            )
        )
