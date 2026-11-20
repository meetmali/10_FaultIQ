from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import FaultEvent, FaultType, Site, Unit

SAMPLE = Path(settings.BASE_DIR) / "sample_data" / "rtu_faulty.csv"


@override_settings(AI_EMBEDDINGS="tfidf", MEDIA_ROOT=Path(settings.BASE_DIR) / "media" / "test")
class WorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("tech", password="pw-123456!")
        self.other = User.objects.create_user("other", password="pw-123456!")
        self.unit = Unit.objects.create(site=Site.objects.create(owner=self.user, name="HQ"), name="RTU-1")
        self.client.login(username="tech", password="pw-123456!")

    def upload(self, data, name="t.csv"):
        return self.client.post(reverse("unit_detail", args=[self.unit.pk]), {"csv_file": SimpleUploadedFile(name, data)}, follow=True)

    def test_library_seeded_by_migration(self):
        self.assertEqual(FaultType.objects.count(), 6)

    def test_upload_detects_named_faults(self):
        r = self.upload(SAMPLE.read_bytes())
        self.assertContains(r, "Insufficient cooling capacity")
        self.assertTrue(FaultEvent.objects.filter(fault_type__code="low-refrigerant").exists())

    def test_bad_csv_fails_gracefully(self):
        r = self.upload(b"a,b\n1,2\n")
        self.assertContains(r, "Missing required columns")

    def test_non_csv_rejected_by_form(self):
        r = self.upload(b"hello", name="x.txt")
        self.assertContains(r, "Upload a .csv file.")

    def test_other_users_cannot_see_unit(self):
        self.client.login(username="other", password="pw-123456!")
        self.assertEqual(self.client.get(reverse("unit_detail", args=[self.unit.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("api_unit_events", args=[self.unit.pk])).status_code, 404)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_review_requires_note_when_confirming(self):
        self.upload(SAMPLE.read_bytes())
        e = FaultEvent.objects.first()
        r = self.client.post(reverse("event_detail", args=[e.pk]), {"review_status": "confirmed", "technician_notes": ""})
        self.assertContains(r, "Add a short note")

    def test_assistant_ranks_and_validates(self):
        r = self.client.post(reverse("assistant"), {"text": "cooling at 100 percent but supply air stays warm"})
        self.assertContains(r, "Insufficient cooling capacity")
        r = self.client.post(reverse("assistant"), {"text": "123 456 789 0"})
        self.assertContains(r, "Use words to describe")

    def test_pages_and_exports_render(self):
        self.upload(SAMPLE.read_bytes())
        e = FaultEvent.objects.first()
        for name, args in [("dashboard", []), ("event_list", []), ("fault_list", []), ("events_csv", []), ("api_summary", []),
                           ("event_detail", [e.pk]), ("analysis_detail", [e.analysis_id]), ("unit_update", [self.unit.pk]),
                           ("fault_detail", ["mat-sensor"])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.assertIn("events", self.client.get(reverse("api_unit_events", args=[self.unit.pk])).json())
