"""Generate synthetic rooftop-unit trend CSVs (no licensed data), with known injected faults."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from diagnostics.sample import FAULTS, generate


class Command(BaseCommand):
    help = "Write synthetic sample CSVs to web/sample_data/."

    def handle(self, *args, **opts):
        out = Path(settings.BASE_DIR) / "sample_data"
        out.mkdir(exist_ok=True)
        generate(faults=FAULTS).to_csv(out / "rtu_faulty.csv", index=False)
        generate(seed=1).to_csv(out / "rtu_healthy.csv", index=False)
        (out / "rtu_faulty_labels.json").write_text(json.dumps(
            [{"fault": c, "start": f"2026-06-{a + 1:02d}", "end": f"2026-06-{b + 1:02d}"} for c, a, b in FAULTS], indent=2))
        self.stdout.write(self.style.SUCCESS(f"Wrote samples to {out}"))
