from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

import datetime

from . import energy
from .models import AssistantQuery, FaultEvent, FaultType, Site, Unit, WorkOrder

SAMPLE = Path(settings.BASE_DIR) / "sample_data" / "rtu_faulty.csv"


@override_settings(
    AI_EMBEDDINGS="tfidf",
    MEDIA_ROOT=Path(settings.BASE_DIR) / "media" / "test",
    STORAGES={**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
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

    def test_signup_loads_sample_portfolio(self):
        self.client.logout()
        r = self.client.post(reverse("signup"), {"username": "newbie", "password1": "Strong-pass-9081", "password2": "Strong-pass-9081"}, follow=True)
        self.assertContains(r, "units have a fault")
        self.assertEqual(Unit.objects.filter(site__owner__username="newbie").count(), 6)
        self.assertTrue(FaultEvent.objects.filter(analysis__unit__site__owner__username="newbie", review_status="confirmed").exists())
        self.assertEqual(WorkOrder.objects.filter(event__analysis__unit__site__owner__username="newbie").count(), 2)
        self.assertTrue(FaultEvent.objects.filter(analysis__unit__site__owner__username="newbie", review_status="rejected").exists())

    # ---------- final features: energy estimate, work orders, feedback, AI quality, health ----------
    def event(self, code="low-refrigerant"):
        self.upload(SAMPLE.read_bytes())
        return FaultEvent.objects.filter(fault_type__code=code).first()

    def test_energy_estimate_is_transparent_arithmetic(self):
        self.unit.tonnage = 10
        self.unit.save()
        e = self.event("low-refrigerant")
        est = energy.estimate(e)
        self.assertEqual(est["kwh"], round(e.hours * 10 * energy.KW_PER_TON * 0.30))
        self.assertGreater(est["monthly_cost"], 0)
        self.assertFalse(est["comfort"])

    def test_work_order_prefilled_validated_and_closing_confirms_fault(self):
        e = self.event("econ-stuck-closed")
        r = self.client.get(reverse("workorder_create", args=[e.pk]))
        self.assertContains(r, "Suggested priority")
        past = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        r = self.client.post(reverse("workorder_create", args=[e.pk]), {"title": "Fix damper", "priority": "high", "status": "open", "due_date": past})
        self.assertContains(r, "cannot be in the past")
        self.client.post(reverse("workorder_create", args=[e.pk]), {"title": "Fix damper", "priority": "high", "status": "open"})
        order = WorkOrder.objects.get(event=e)
        r = self.client.post(reverse("workorder_detail", args=[order.pk]), {"title": "Fix damper", "priority": "high", "status": "done", "notes": ""})
        self.assertContains(r, "Describe what was found")
        self.client.post(reverse("workorder_detail", args=[order.pk]), {"title": "Fix damper", "priority": "high", "status": "done", "notes": "Actuator linkage loose, fixed."})
        order.refresh_from_db()
        e.refresh_from_db()
        self.assertIsNotNone(order.completed_at)
        self.assertEqual(e.review_status, "confirmed")
        self.assertEqual(e.technician_notes, "Actuator linkage loose, fixed.")
        self.assertEqual(self.client.get(reverse("api_work_orders")).json()["work_orders"][0]["status"], "done")
        self.assertContains(self.client.get(reverse("workorder_list")), "Fix damper")

    def test_work_orders_are_private(self):
        e = self.event()
        order = WorkOrder.objects.create(event=e, title="Mine")
        self.client.login(username="other", password="pw-123456!")
        self.assertEqual(self.client.get(reverse("workorder_detail", args=[order.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("workorder_create", args=[e.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("api_work_orders")).json()["work_orders"], [])

    def test_assistant_feedback_counts_on_quality_page(self):
        self.client.post(reverse("assistant"), {"text": "cooling at 100 percent but supply air stays warm"})
        q = AssistantQuery.objects.get(user=self.user)
        self.client.post(reverse("assistant_feedback", args=[q.pk]), {"helpful": "yes"})
        q.refresh_from_db()
        self.assertTrue(q.helpful)
        r = self.client.get(reverse("quality"))
        self.assertContains(r, "100%")
        self.client.login(username="other", password="pw-123456!")
        self.assertEqual(self.client.post(reverse("assistant_feedback", args=[q.pk]), {"helpful": "no"}).status_code, 404)

    def test_health_check(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("healthz")).json()["status"], "ok")
