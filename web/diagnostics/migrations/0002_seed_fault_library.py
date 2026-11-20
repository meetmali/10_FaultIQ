from django.db import migrations

from diagnostics.library import FAULTS


def seed(apps, schema_editor):
    FaultType = apps.get_model("diagnostics", "FaultType")
    for f in FAULTS:
        FaultType.objects.update_or_create(code=f["code"], defaults=f)


def unseed(apps, schema_editor):
    apps.get_model("diagnostics", "FaultType").objects.filter(code__in=[f["code"] for f in FAULTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("diagnostics", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
