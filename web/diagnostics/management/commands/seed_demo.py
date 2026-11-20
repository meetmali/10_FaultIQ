"""Create a demo user, a site, a unit and one analysis of the faulty sample."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from diagnostics.models import Site, Unit
from diagnostics.services import run_analysis


class Command(BaseCommand):
    help = "Create demo data. Username 'demo'; the password is printed once."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=None)

    def handle(self, *args, password=None, **opts):
        import secrets

        User = get_user_model()
        user, created = User.objects.get_or_create(username="demo")
        if created or password:
            password = password or secrets.token_urlsafe(9)
            user.set_password(password)
            user.save()
            self.stdout.write(f"demo password: {password}")
        site, _ = Site.objects.get_or_create(owner=user, name="Campus North", defaults={"city": "Champaign, IL"})
        unit, _ = Unit.objects.get_or_create(site=site, name="RTU-1", defaults={"tonnage": 10})
        Unit.objects.get_or_create(site=site, name="RTU-2", defaults={"tonnage": 15})
        path = Path(settings.BASE_DIR) / "sample_data" / "rtu_faulty.csv"
        if not unit.analyses.exists():
            a = run_analysis(unit, SimpleUploadedFile(path.name, path.read_bytes(), "text/csv"))
            self.stdout.write(f"analysis {a.pk}: {a.status}, {a.events.count()} events")
        self.stdout.write(self.style.SUCCESS("Demo data ready"))
