import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create or update the staff account used to sign in to /manage/, "
        "using the ADMIN_USERNAME and ADMIN_PASSWORD environment variables."
    )

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")

        if not username or not password:
            raise CommandError(
                "ADMIN_USERNAME and ADMIN_PASSWORD must both be set in the "
                "environment. Copy .env.example to .env and fill them in."
            )

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        user.set_password(password)
        user.is_staff = True
        user.is_active = True
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} staff account '{username}'.")
        )
