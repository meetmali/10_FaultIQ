from django.db import migrations

from diagnostics.sample import add_sample_history


def backfill(apps, schema_editor):
    """Give accounts created before work orders existed the same sample history as new accounts."""
    Site = apps.get_model("diagnostics", "Site")
    FaultEvent = apps.get_model("diagnostics", "FaultEvent")
    WorkOrder = apps.get_model("diagnostics", "WorkOrder")
    for owner_id in Site.objects.filter(name="Campus North").values_list("owner_id", flat=True).distinct():
        add_sample_history(owner_id, FaultEvent, WorkOrder)


class Migration(migrations.Migration):
    dependencies = [("diagnostics", "0003_work_orders_and_feedback")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
