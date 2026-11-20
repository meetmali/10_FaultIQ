"""Glue between the AI modules and the database."""

import logging
import time
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .ai import assistant
from .ai.detection import DetectionError, detect
from .models import Analysis, AssistantQuery, FaultEvent, FaultType

log = logging.getLogger(__name__)


def _aware(ts):
    return timezone.make_aware(ts.to_pydatetime(), dt_timezone.utc) if ts.tzinfo is None else ts.to_pydatetime()


def run_analysis(unit, upload) -> Analysis:
    """Store the upload, run detection and save the events. Failures are recorded, never raised."""
    data = upload.read()
    upload.seek(0)
    analysis = Analysis(unit=unit, csv_file=upload, original_name=upload.name[:255])
    started = time.perf_counter()
    try:
        result = detect(data)
    except DetectionError as exc:
        analysis.status, analysis.error = Analysis.Status.FAILED, str(exc)
    except Exception:
        log.exception("Detection crashed for unit %s", unit.pk)
        analysis.status, analysis.error = Analysis.Status.FAILED, "Analysis failed unexpectedly. The error was logged."
    else:
        analysis.status = Analysis.Status.DONE
        analysis.hours_analysed, analysis.anomaly_hours = result.hours_analysed, result.anomaly_hours
        analysis.rows_dropped, analysis.series = result.rows_dropped, result.series
    analysis.duration_ms = int((time.perf_counter() - started) * 1000)
    with transaction.atomic():
        analysis.save()
        if analysis.status == Analysis.Status.DONE:
            types = {f.code: f for f in FaultType.objects.all()}
            FaultEvent.objects.bulk_create(
                FaultEvent(
                    analysis=analysis, fault_type=types.get(e.fault_code), starts_at=_aware(e.start),
                    ends_at=_aware(e.end), hours=e.hours, confidence=e.confidence, anomaly_score=e.anomaly_score,
                )
                for e in result.events
            )
    log.info("analysis %s unit=%s status=%s ms=%s", analysis.pk, unit.pk, analysis.status, analysis.duration_ms)
    return analysis


def over_rate_limit(user) -> bool:
    since = timezone.now() - timedelta(hours=1)
    return AssistantQuery.objects.filter(user=user, created_at__gte=since).count() >= settings.ASSISTANT_HOURLY_LIMIT


def run_assistant(user, text, event=None) -> AssistantQuery:
    """Rank likely faults for a symptom description, using the library and the user's confirmed cases."""
    faults = list(FaultType.objects.values("code", "name", "symptoms", "causes", "checks"))
    confirmed = FaultEvent.objects.filter(
        analysis__unit__site__owner=user, review_status=FaultEvent.Review.CONFIRMED
    ).exclude(technician_notes="").select_related("fault_type")
    cases = [{"id": e.pk, "label": e.label, "notes": e.technician_notes} for e in confirmed[:200]]
    if event is not None:
        # The detector's finding is context for the assistant, not a replacement for the user's words.
        text = f"{text} (Detector flagged: {event.label})"
    started = time.perf_counter()
    results = assistant.diagnose(text, faults, cases)
    latency = int((time.perf_counter() - started) * 1000)
    return AssistantQuery.objects.create(
        user=user, event=event, text=text, results=results, backend=results["backend"], latency_ms=latency
    )
