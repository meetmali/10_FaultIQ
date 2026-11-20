"""Run the evaluation suite and print Markdown results (used for docs/P2_REPORT.md)."""

import json
import time
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction

from diagnostics.ai import assistant
from diagnostics.ai.detection import detect
from diagnostics.models import FaultType, Site, Unit
from diagnostics.services import run_analysis, run_assistant

SAMPLES = Path(settings.BASE_DIR) / "sample_data"

# Labelled symptom descriptions, written the way a technician would phrase them.
ASSISTANT_SET = [
    ("Supply air stays around 18 C even though the compressor is at 100 percent on a hot afternoon", "low-refrigerant"),
    ("Rooms get warm every afternoon, unit runs flat out and never reaches setpoint", "low-refrigerant"),
    ("It is 12 degrees outside but the outdoor air damper stays shut while the compressor runs", "econ-stuck-closed"),
    ("No free cooling on mild mornings, mixed air is the same as return air", "econ-stuck-closed"),
    ("Damper wide open at 35 C outside, coil struggling and the space feels humid", "econ-stuck-open"),
    ("Mixed air reads 30 C when outside is 20 and return is 23, that cannot be right", "mat-sensor"),
    ("Mixed air temperature reading looks impossible and the economizer hunts", "mat-sensor"),
    ("Cooling command is zero but discharge air is ice cold", "cooling-leak"),
    ("No airflow from the diffusers during the day and the belt squeals", "fan-off-occupied"),
    ("Fan does not start in the morning, offices are stuffy", "fan-off-occupied"),
]


def labelled_events(path, **kw):
    labels = json.loads((SAMPLES / "rtu_faulty_labels.json").read_text()) if "faulty" in path.name else []
    r = detect(path.read_bytes(), **kw)
    hit = {lab["fault"] for lab in labels for e in r.events
           if e.fault_code == lab["fault"] and lab["start"] <= str(e.start.date()) <= lab["end"]}
    false = [e for e in r.events if not any(lab["start"] <= str(e.start.date()) <= lab["end"] for lab in labels)]
    return r, len(hit), len(labels), len(false)


class Command(BaseCommand):
    help = "Evaluate detection and the AI assistant."

    def handle(self, *args, **opts):
        out = []
        with transaction.atomic():
            user = get_user_model().objects.create(username="__eval__")
            unit = Unit.objects.create(site=Site.objects.create(owner=user, name="Eval"), name="RTU-E")

            def upload(name, data):
                t = time.perf_counter()
                a = run_analysis(unit, SimpleUploadedFile(name, data, "text/csv"))
                return a, int((time.perf_counter() - t) * 1000)

            a, ms = upload("rtu_faulty.csv", (SAMPLES / "rtu_faulty.csv").read_bytes())
            out.append(("Upload rtu_faulty.csv (21 days, 4 injected faults)", ", ".join(sorted({e.label for e in a.events.all()})) + f" ({a.events.count()} events)", ms))
            a, ms = upload("rtu_healthy.csv", (SAMPLES / "rtu_healthy.csv").read_bytes())
            out.append(("Upload rtu_healthy.csv (no faults)", f"{a.events.count()} events: " + ", ".join(f"{e.label} {e.hours} h" for e in a.events.all()), ms))
            a, ms = upload("broken.csv", b"timestamp,oat,sat\n2026-06-01 00:00,20,13\n")
            out.append(("Upload CSV missing columns", f"{a.status}: {a.error}", ms))
            for text in (ASSISTANT_SET[0][0], "My laptop screen flickers when I open the browser"):
                q = run_assistant(user, text)
                m = q.results["matches"][0]
                out.append((f"Assistant: {text}", f"top: {m['name']} ({m['score']}), confident={q.results['confident']}", q.latency_ms))
            transaction.set_rollback(True)

        self.stdout.write("## Tests\n| # | Input | Actual output | Latency |\n|---|---|---|---|")
        for i, (inp, actual, ms) in enumerate(out, 1):
            self.stdout.write(f"| {i} | {inp} | {actual} | {ms} ms |")

        self.stdout.write("\n## Detection improvement (min_unexplained_hours)\n| Setting | File | Faults found | False events |\n|---|---|---|---|")
        for m in (2, 4):
            for f in ("rtu_faulty.csv", "rtu_healthy.csv"):
                r, hit, total, false = labelled_events(SAMPLES / f, min_unexplained_hours=m)
                self.stdout.write(f"| {m} h | {f} | {hit}/{total} | {false} |")

        self.stdout.write("\n## Assistant top-1 accuracy (10 labelled descriptions)\n| Backend | Top-1 | Top-3 | Mean latency |\n|---|---|---|---|")
        faults = list(FaultType.objects.values("code", "name", "symptoms", "causes", "checks"))
        for backend in ("tfidf", "bge", "hybrid"):
            settings.AI_EMBEDDINGS = backend
            top1 = top3 = 0
            t = time.perf_counter()
            for text, code in ASSISTANT_SET:
                res = assistant.diagnose(text, faults, [])
                codes = [m["code"] for m in res["matches"]]
                top1 += codes[0] == code
                top3 += code in codes
            ms = (time.perf_counter() - t) * 1000 / len(ASSISTANT_SET)
            self.stdout.write(f"| {res['backend']} | {top1}/10 | {top3}/10 | {ms:.0f} ms |")
