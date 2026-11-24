from django.conf import settings
from django.db import models
from django.urls import reverse


class FaultType(models.Model):
    """An entry in the rooftop-unit fault library. Also the corpus for the AI assistant."""

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    component = models.CharField(max_length=80)
    symptoms = models.TextField()
    causes = models.TextField()
    checks = models.TextField(help_text="What a technician should check first.")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("fault_detail", args=[self.code])


class Site(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sites")
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_site_per_owner")]

    def __str__(self):
        return self.name


class Unit(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=120)
    tonnage = models.PositiveIntegerField(null=True, blank=True, help_text="Nominal cooling capacity in tons.")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["site__name", "name"]

    def __str__(self):
        return f"{self.site.name} / {self.name}"

    def get_absolute_url(self):
        return reverse("unit_detail", args=[self.pk])


class Analysis(models.Model):
    class Status(models.TextChoices):
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="analyses")
    csv_file = models.FileField(upload_to="uploads/%Y/%m/")
    original_name = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices)
    error = models.TextField(blank=True)
    hours_analysed = models.PositiveIntegerField(default=0)
    anomaly_hours = models.PositiveIntegerField(default=0)
    rows_dropped = models.PositiveIntegerField(default=0)
    series = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "analyses"

    def __str__(self):
        return f"{self.unit} {self.created_at:%Y-%m-%d %H:%M}"

    def get_absolute_url(self):
        return reverse("analysis_detail", args=[self.pk])


class FaultEvent(models.Model):
    class Review(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="events")
    fault_type = models.ForeignKey(FaultType, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    hours = models.PositiveIntegerField()
    confidence = models.FloatField()
    anomaly_score = models.FloatField()
    review_status = models.CharField(max_length=12, choices=Review.choices, default=Review.UNREVIEWED)
    technician_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return f"{self.label} at {self.starts_at:%Y-%m-%d %H:%M}"

    @property
    def label(self):
        return self.fault_type.name if self.fault_type else "Unclassified anomaly"

    def get_absolute_url(self):
        return reverse("event_detail", args=[self.pk])


class AssistantQuery(models.Model):
    """One run of the AI diagnostic assistant, kept for history and evaluation."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_queries")
    event = models.ForeignKey(FaultEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="assistant_queries")
    text = models.TextField()
    results = models.JSONField(default=dict)
    backend = models.CharField(max_length=40)
    latency_ms = models.PositiveIntegerField()
    helpful = models.BooleanField(null=True, blank=True, help_text="Technician feedback: was the top answer right?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "assistant queries"


class WorkOrder(models.Model):
    """A repair job for one fault event. Closing it with notes confirms the fault and teaches the assistant."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        URGENT = "urgent", "Urgent"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    event = models.OneToOneField(FaultEvent, on_delete=models.CASCADE, related_name="work_order")
    title = models.CharField(max_length=160)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    assignee = models.CharField(max_length=120, blank=True, help_text="Technician or contractor.")
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="What was found and fixed. Required to close the work order.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "priority"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("workorder_detail", args=[self.pk])

    @property
    def unit(self):
        return self.event.analysis.unit
