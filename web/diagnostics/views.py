import csv
import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import connection
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import energy
from .ai.assistant import AssistantError
from .forms import AssistantForm, ReviewForm, SignUpForm, SiteForm, UnitForm, UploadForm, WorkOrderForm
from .models import Analysis, AssistantQuery, FaultEvent, FaultType, Site, Unit, WorkOrder
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


def _work_orders(user):
    return WorkOrder.objects.filter(event__analysis__unit__site__owner=user).select_related(
        "event__fault_type", "event__analysis__unit__site")


def _repaired(event):
    try:
        return event.work_order.status == WorkOrder.Status.DONE
    except WorkOrder.DoesNotExist:
        return False


def unit_monthly_cost(events):
    """Monthly cost if left unfixed, counting each distinct fault on a unit once and skipping repaired faults."""
    repaired = {e.fault_type_id for e in events if _repaired(e)}
    by_code = {}
    for e in events:
        if e.fault_type_id in repaired:
            continue
        by_code[e.fault_type_id] = max(by_code.get(e.fault_type_id, 0), energy.estimate(e)["monthly_cost"])
    return sum(by_code.values())


def unit_health(unit):
    """Status of a unit from its latest analysis: fault (named fault), unclear (unexplained only), normal, off."""
    analysis = unit.analyses.filter(status=Analysis.Status.DONE).first()
    events = list(analysis.events.exclude(review_status=FaultEvent.Review.REJECTED).select_related("fault_type", "work_order")) if analysis else []
    named = sorted((e for e in events if e.fault_type), key=lambda e: -e.hours)
    state = "off" if analysis is None else "fault" if named else "unclear" if events else "normal"
    top = named[0] if named else (events[0] if events else None)
    share = analysis.anomaly_hours / analysis.hours_analysed if analysis and analysis.hours_analysed else 0
    return {"unit": unit, "analysis": analysis, "state": state, "label": STATE_LABEL[state], "top": top,
            "events": events, "fault_hours": sum(e.hours for e in events), "share": round(share * 100),
            "monthly_cost": unit_monthly_cost(events)}


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
        "monthly_cost": sum(h["monthly_cost"] for h in health),
        "open_orders": _work_orders(request.user).exclude(status=WorkOrder.Status.DONE).count(),
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
    events = list(events.order_by("-starts_at")[:300])
    for e in events:
        e.est = energy.estimate(e)
    return render(request, "diagnostics/event_list.html", {"events": events, "status": status, "statuses": FaultEvent.Review.choices})


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
        "history": event.assistant_queries.all()[:3], "est": energy.estimate(event),
        "work_order": WorkOrder.objects.filter(event=event).first(), "price": energy.price(),
    })


# ---------- work orders: turn a fault into a tracked repair job ----------
PRIORITY_RANK = {p: i for i, p in enumerate(WorkOrder.Priority.values)}
STATUS_RANK = {WorkOrder.Status.IN_PROGRESS: 0, WorkOrder.Status.OPEN: 1, WorkOrder.Status.DONE: 2}


def _apply_status(order):
    """Closing a work order records the time and confirms the fault with the repair notes.
    Confirmed faults with notes become past cases the AI assistant can match against."""
    if order.status == WorkOrder.Status.DONE:
        order.completed_at = order.completed_at or timezone.now()
        event = order.event
        if event.review_status != FaultEvent.Review.CONFIRMED:
            event.review_status = FaultEvent.Review.CONFIRMED
            event.technician_notes = event.technician_notes or order.notes
            event.save(update_fields=["review_status", "technician_notes"])
    else:
        order.completed_at = None


@login_required
def workorder_list(request):
    orders = _work_orders(request.user)
    status = request.GET.get("status", "")
    counts = dict(orders.values_list("status").annotate(n=Count("id")))
    done = orders.filter(status=WorkOrder.Status.DONE, completed_at__isnull=False)
    hours = [(o.completed_at - o.created_at).total_seconds() / 3600 for o in done]
    if status in WorkOrder.Status.values:
        orders = orders.filter(status=status)
    orders = sorted(orders[:300], key=lambda o: (STATUS_RANK[o.status], PRIORITY_RANK[o.priority], o.due_date or date.max))
    for o in orders:
        o.est = energy.estimate(o.event)
    return render(request, "diagnostics/workorder_list.html", {
        "orders": orders, "status": status, "statuses": WorkOrder.Status.choices, "today": date.today(),
        "counts": {k: counts.get(k, 0) for k in WorkOrder.Status.values},
        "mttr": round(sum(hours) / len(hours), 1) if hours else None,
        "open_cost": sum(o.est["monthly_cost"] for o in orders if o.status != WorkOrder.Status.DONE),
    })


@login_required
def workorder_create(request, event_pk):
    event = get_object_or_404(_events(request.user), pk=event_pk)
    existing = WorkOrder.objects.filter(event=event).first()
    if existing:
        return redirect(existing)
    priority = energy.suggest_priority(event)
    initial = {"title": f"{event.label} on {event.analysis.unit.name}", "priority": priority,
               "due_date": date.today() + timedelta(days=energy.DUE_DAYS[priority])}
    form = WorkOrderForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.event = event
        _apply_status(order)
        order.save()
        messages.success(request, f"Work order created with {order.get_priority_display().lower()} priority.")
        return redirect(order)
    return render(request, "diagnostics/workorder_form.html", {
        "form": form, "event": event, "est": energy.estimate(event), "suggested": priority, "price": energy.price(),
    })


@login_required
def workorder_detail(request, pk):
    order = get_object_or_404(_work_orders(request.user), pk=pk)
    was_done = order.status == WorkOrder.Status.DONE
    form = WorkOrderForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        _apply_status(order)
        order.save()
        if order.status == WorkOrder.Status.DONE and not was_done:
            messages.success(request, "Work order closed. The fault is confirmed and the AI assistant can now match new problems against this repair.")
        else:
            messages.success(request, "Work order updated.")
        return redirect(order)
    return render(request, "diagnostics/workorder_form.html", {
        "form": form, "order": order, "event": order.event, "est": energy.estimate(order.event), "price": energy.price(),
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


@login_required
@require_POST
def assistant_feedback(request, pk):
    """Thumbs up or down on the assistant's top answer. Feeds the live accuracy figure on the AI quality page."""
    query = get_object_or_404(AssistantQuery, pk=pk, user=request.user)
    value = request.POST.get("helpful")
    if value in ("yes", "no"):
        query.helpful = value == "yes"
        query.save(update_fields=["helpful"])
        messages.success(request, "Thanks. Your feedback is counted on the AI quality page.")
    return redirect(query.event if query.event_id else "assistant")


# Offline benchmark from `python manage.py evaluate` (docs/P2_REPORT.md, Part 4).
BENCHMARK = {
    "detection": [("Injected faults found in the labelled test file", "4 of 4"),
                  ("False events on the healthy and faulty files", "2 (25 before the 4-hour rule)")],
    "assistant": [("Hybrid: bge-small + TF-IDF (default)", "9/10", "10/10"), ("bge-small embeddings only", "8/10", "10/10"),
                  ("TF-IDF only (the free hosted site)", "9/10", "10/10")],
}


@login_required
def quality(request):
    """How well the AI is doing, measured from this account's own technician reviews and feedback."""
    rows = list(_events(request.user).values("fault_type__name").annotate(
        total=Count("id"),
        confirmed=Count("id", filter=Q(review_status=FaultEvent.Review.CONFIRMED)),
        rejected=Count("id", filter=Q(review_status=FaultEvent.Review.REJECTED)),
    ).order_by("-total"))
    for r in rows:
        reviewed = r["confirmed"] + r["rejected"]
        r["precision"] = round(100 * r["confirmed"] / reviewed) if reviewed else None
    confirmed, rejected = sum(r["confirmed"] for r in rows), sum(r["rejected"] for r in rows)
    queries = AssistantQuery.objects.filter(user=request.user)
    a = queries.aggregate(n=Count("id"), rated=Count("id", filter=Q(helpful__isnull=False)),
                          helpful=Count("id", filter=Q(helpful=True)), avg_ms=Avg("latency_ms"))
    a["confident"] = queries.filter(results__confident=True).count()
    a["helpful_rate"] = round(100 * a["helpful"] / a["rated"]) if a["rated"] else None
    a["confident_rate"] = round(100 * a["confident"] / a["n"]) if a["n"] else None
    return render(request, "diagnostics/quality.html", {
        "rows": rows, "confirmed": confirmed, "rejected": rejected,
        "precision": round(100 * confirmed / (confirmed + rejected)) if confirmed + rejected else None,
        "a": a, "backend": settings.AI_EMBEDDINGS, "benchmark": BENCHMARK,
        "factors": sorted(energy.WASTE_FACTOR.items(), key=lambda kv: -kv[1]), "price": energy.price(),
        "kw_per_ton": energy.KW_PER_TON, "hours_per_month": energy.HOURS_PER_MONTH,
    })


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


@login_required
@require_GET
def api_work_orders(request):
    orders = _work_orders(request.user)
    return JsonResponse({"work_orders": [
        {"id": o.pk, "title": o.title, "unit": o.unit.name, "fault": o.event.fault_type.code if o.event.fault_type_id else None,
         "priority": o.priority, "status": o.status, "assignee": o.assignee,
         "due_date": o.due_date.isoformat() if o.due_date else None,
         "monthly_cost_usd": energy.estimate(o.event)["monthly_cost"]}
        for o in orders
    ]})


@require_GET
def healthz(request):
    """Uptime check: the app is up and the database answers."""
    try:
        connection.ensure_connection()
        ok = True
    except Exception:
        ok = False
    return JsonResponse({"status": "ok" if ok else "degraded", "database": ok, "ai_backend": settings.AI_EMBEDDINGS},
                        status=200 if ok else 503)
