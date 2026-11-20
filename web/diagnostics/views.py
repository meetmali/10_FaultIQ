import csv
import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .ai.assistant import AssistantError
from .forms import AssistantForm, ReviewForm, SignUpForm, SiteForm, UnitForm, UploadForm
from .models import Analysis, AssistantQuery, FaultEvent, FaultType, Site, Unit
from .sample import load_sample_portfolio
from .services import over_rate_limit, run_analysis, run_assistant

STATE_LABEL = {"fault": "Fault", "unclear": "Check", "normal": "Healthy", "off": "No data"}
EXAMPLES = [
    "Supply air stays warm even though the compressor runs at 100% on hot afternoons",
    "Outdoor air damper stays shut on cool mornings while the compressor runs",
    "Mixed air temperature reads hotter than both outdoor and return air",
]


# ---------- ownership helpers: every query is scoped to the signed-in user ----------
def _units(user):
    return Unit.objects.filter(site__owner=user).select_related("site")


def _events(user):
    return FaultEvent.objects.filter(analysis__unit__site__owner=user).select_related("fault_type", "analysis__unit__site")


def unit_health(unit):
    """Status of a unit from its latest analysis: fault (named fault), unclear (unexplained only), normal, off."""
    analysis = unit.analyses.filter(status=Analysis.Status.DONE).first()
    events = list(analysis.events.exclude(review_status=FaultEvent.Review.REJECTED).select_related("fault_type")) if analysis else []
    named = sorted((e for e in events if e.fault_type), key=lambda e: -e.hours)
    state = "off" if analysis is None else "fault" if named else "unclear" if events else "normal"
    top = named[0] if named else (events[0] if events else None)
    share = analysis.anomaly_hours / analysis.hours_analysed if analysis and analysis.hours_analysed else 0
    return {"unit": unit, "analysis": analysis, "state": state, "label": STATE_LABEL[state], "top": top,
            "events": events, "fault_hours": sum(e.hours for e in events), "share": round(share * 100)}


# ---------- public pages ----------
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "diagnostics/home.html")


def signup(request):
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        load_sample_portfolio(user)
        messages.success(request, "Account created. A sample portfolio of six rooftop units is loaded and analysed.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


def fault_list(request):
    q = request.GET.get("q", "").strip()
    component = request.GET.get("component", "")
    faults = FaultType.objects.all()
    if q:
        faults = faults.filter(Q(name__icontains=q) | Q(symptoms__icontains=q) | Q(causes__icontains=q))
    if component:
        faults = faults.filter(component=component)
    components = FaultType.objects.order_by("component").values_list("component", flat=True).distinct()
    return render(request, "diagnostics/fault_list.html", {"faults": faults, "q": q, "component": component, "components": components})


def fault_detail(request, code):
    return render(request, "diagnostics/fault_detail.html", {"fault": get_object_or_404(FaultType, code=code)})


# ---------- dashboard ----------
@login_required
def dashboard(request):
    if not Unit.objects.filter(site__owner=request.user).exists():
        load_sample_portfolio(request.user)
    events = _events(request.user)
    by_fault = events.exclude(review_status=FaultEvent.Review.REJECTED).values("fault_type__name").annotate(n=Count("id"), hours=Sum("hours")).order_by("-hours")
    health = [unit_health(u) for u in _units(request.user)]
    attention = sorted((h for h in health if h["state"] in ("fault", "unclear")), key=lambda h: (h["state"] != "fault", -h["fault_hours"]))
    stats = {
        "units": len(health),
        "healthy": sum(h["state"] != "fault" for h in health),
        "faults": sum(h["state"] == "fault" for h in health),
        "fault_hours": sum(h["fault_hours"] for h in health),
        "unreviewed": events.filter(review_status=FaultEvent.Review.UNREVIEWED).count(),
        "confirmed": events.filter(review_status=FaultEvent.Review.CONFIRMED).count(),
    }
    chart = {"labels": [r["fault_type__name"] or "Unclassified anomaly" for r in by_fault], "hours": [r["hours"] for r in by_fault]}
    return render(request, "diagnostics/dashboard.html", {
        "stats": stats, "health": health, "attention": attention, "by_fault": by_fault, "chart": json.dumps(chart),
        "has_sample": Site.objects.filter(owner=request.user, name="Campus North").exists(),
    })


@login_required
@require_POST
def load_sample(request):
    load_sample_portfolio(request.user)
    messages.success(request, "Sample portfolio loaded: six units with analyses already run.")
    return redirect("dashboard")


# ---------- sites and units (CRUD) ----------
@login_required
def site_create(request):
    form = SiteForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        site = form.save(commit=False)
        site.owner = request.user
        site.save()
        messages.success(request, f"Site '{site.name}' added.")
        return redirect("unit_create")
    return render(request, "diagnostics/form.html", {"form": form, "title": "Add a site"})


@login_required
def unit_create(request):
    if not Site.objects.filter(owner=request.user).exists():
        messages.info(request, "Add a site first. Units belong to a site.")
        return redirect("site_create")
    form = UnitForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        unit = form.save()
        messages.success(request, f"Unit '{unit.name}' added. Upload a trend export to analyse it.")
        return redirect(unit)
    return render(request, "diagnostics/form.html", {"form": form, "title": "Add a rooftop unit"})


@login_required
def unit_update(request, pk):
    unit = get_object_or_404(_units(request.user), pk=pk)
    form = UnitForm(request.POST or None, instance=unit, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Unit updated.")
        return redirect(unit)
    return render(request, "diagnostics/form.html", {"form": form, "title": f"Edit {unit.name}"})


@login_required
def unit_delete(request, pk):
    unit = get_object_or_404(_units(request.user), pk=pk)
    if request.method == "POST":
        unit.delete()
        messages.success(request, f"Unit '{unit.name}' and its analyses were deleted.")
        return redirect("dashboard")
    return render(request, "diagnostics/confirm_delete.html", {"object": unit})


@login_required
def unit_detail(request, pk):
    unit = get_object_or_404(_units(request.user), pk=pk)
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        analysis = run_analysis(unit, form.cleaned_data["csv_file"])
        if analysis.status == Analysis.Status.DONE:
            messages.success(request, f"Analysis finished: {analysis.events.count()} fault events in {analysis.hours_analysed} running hours.")
        else:
            messages.error(request, f"Analysis failed: {analysis.error}")
        return redirect(analysis)
    return render(request, "diagnostics/unit_detail.html", {
        "unit": unit, "form": form, "h": unit_health(unit), "analyses": unit.analyses.annotate(n=Count("events")),
    })


@login_required
def analysis_detail(request, pk):
    analysis = get_object_or_404(Analysis.objects.filter(unit__site__owner=request.user).select_related("unit__site"), pk=pk)
    return render(request, "diagnostics/analysis_detail.html", {
        "analysis": analysis, "events": analysis.events.select_related("fault_type"), "series": json.dumps(analysis.series),
    })


@login_required
def event_list(request):
    events = _events(request.user)
    status = request.GET.get("status", "")
    if status in FaultEvent.Review.values:
        events = events.filter(review_status=status)
    return render(request, "diagnostics/event_list.html", {"events": events.order_by("-starts_at")[:300], "status": status, "statuses": FaultEvent.Review.choices})


@login_required
def event_detail(request, pk):
    event = get_object_or_404(_events(request.user), pk=pk)
    form = ReviewForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Review saved.")
        return redirect(event)
    return render(request, "diagnostics/event_detail.html", {
        "event": event, "form": form, "assistant_form": AssistantForm(),
        "history": event.assistant_queries.all()[:3],
    })


# ---------- AI assistant ----------
@login_required
def assistant_view(request):
    form = AssistantForm(request.POST or None)
    event = None
    if request.GET.get("event") or request.POST.get("event"):
        event = get_object_or_404(_events(request.user), pk=request.GET.get("event") or request.POST.get("event"))
    result = None
    if request.method == "POST" and form.is_valid():
        if over_rate_limit(request.user):
            messages.error(request, "You have reached the hourly limit for assistant queries. Try again later.")
        else:
            try:
                result = run_assistant(request.user, form.cleaned_data["text"], event)
            except AssistantError as exc:
                form.add_error("text", str(exc))
            except Exception:
                messages.error(request, "The AI assistant is unavailable right now. The fault library still works.")
    history = AssistantQuery.objects.filter(user=request.user)[:5]
    return render(request, "diagnostics/assistant.html", {"form": form, "result": result, "event": event, "history": history, "examples": EXAMPLES})


# ---------- data features: CSV export and JSON API ----------
@login_required
@require_GET
def events_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="faultiq-events.csv"'
    writer = csv.writer(response)
    writer.writerow(["site", "unit", "fault", "starts_at", "ends_at", "hours", "confidence", "review_status", "notes"])
    for e in _events(request.user).order_by("starts_at"):
        u = e.analysis.unit
        writer.writerow([u.site.name, u.name, e.label, e.starts_at.isoformat(), e.ends_at.isoformat(), e.hours, e.confidence, e.review_status, e.technician_notes])
    return response


@login_required
@require_GET
def api_unit_events(request, pk):
    unit = get_object_or_404(_units(request.user), pk=pk)
    events = _events(request.user).filter(analysis__unit=unit).order_by("starts_at")
    return JsonResponse({
        "unit": {"id": unit.pk, "name": unit.name, "site": unit.site.name},
        "events": [
            {"id": e.pk, "fault": e.fault_type.code if e.fault_type else None, "label": e.label,
             "starts_at": e.starts_at.isoformat(), "ends_at": e.ends_at.isoformat(), "hours": e.hours,
             "confidence": e.confidence, "review_status": e.review_status}
            for e in events
        ],
    })


@login_required
@require_GET
def api_summary(request):
    rows = _events(request.user).values("fault_type__code").annotate(events=Count("id"), hours=Sum("hours"))
    return JsonResponse({"faults": [{"fault": r["fault_type__code"], "events": r["events"], "hours": r["hours"]} for r in rows]})


@login_required
@require_POST
def api_assistant(request):
    """POST {"text": "..."} -> ranked faults. Same logic as the assistant page."""
    if over_rate_limit(request.user):
        return JsonResponse({"error": "rate_limited"}, status=429)
    try:
        payload = json.loads(request.body or b"{}")
        q = run_assistant(request.user, str(payload.get("text", "")))
    except (json.JSONDecodeError, AssistantError) as exc:
        return JsonResponse({"error": str(exc) or "invalid JSON"}, status=400)
    return JsonResponse({**q.results, "latency_ms": q.latency_ms})
