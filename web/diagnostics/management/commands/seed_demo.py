"""Create the demo user with the sample portfolio already analysed."""

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from diagnostics.sample import load_sample_portfolio


class Command(BaseCommand):
    help = "Create demo data. Username 'demo'; the password is printed once if generated."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=None)

    def handle(self, *args, password=None, **opts):
        user, created = get_user_model().objects.get_or_create(username="demo")
        if created or password:
            password = password or secrets.token_urlsafe(9)
            user.set_password(password)
            user.save()
            self.stdout.write(f"demo password: {password}")
        load_sample_portfolio(user)
        self.stdout.write(self.style.SUCCESS("Demo data ready"))
