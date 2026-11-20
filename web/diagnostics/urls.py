from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("sites/new/", views.site_create, name="site_create"),
    path("units/new/", views.unit_create, name="unit_create"),
    path("units/<int:pk>/", views.unit_detail, name="unit_detail"),
    path("units/<int:pk>/edit/", views.unit_update, name="unit_update"),
    path("units/<int:pk>/delete/", views.unit_delete, name="unit_delete"),
    path("analyses/<int:pk>/", views.analysis_detail, name="analysis_detail"),
    path("events/", views.event_list, name="event_list"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/export.csv", views.events_csv, name="events_csv"),
    path("assistant/", views.assistant_view, name="assistant"),
    path("library/", views.fault_list, name="fault_list"),
    path("library/<slug:code>/", views.fault_detail, name="fault_detail"),
    path("api/units/<int:pk>/events/", views.api_unit_events, name="api_unit_events"),
    path("api/summary/", views.api_summary, name="api_summary"),
    path("api/assistant/", views.api_assistant, name="api_assistant"),
]
