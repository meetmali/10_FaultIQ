from django.contrib import admin

from .models import Analysis, AssistantQuery, FaultEvent, FaultType, Site, Unit, WorkOrder

admin.site.register([FaultType, Site, Unit, AssistantQuery])


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ["unit", "status", "hours_analysed", "anomaly_hours", "created_at"]
    exclude = ["series"]


@admin.register(FaultEvent)
class FaultEventAdmin(admin.ModelAdmin):
    list_display = ["analysis", "fault_type", "starts_at", "hours", "confidence", "review_status"]
    list_filter = ["review_status", "fault_type"]


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ["title", "priority", "status", "assignee", "due_date", "completed_at"]
    list_filter = ["status", "priority"]
    search_fields = ["title", "assignee", "notes"]
