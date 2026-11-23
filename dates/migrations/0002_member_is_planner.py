from django.db import migrations, models


def mark_partners(apps, schema_editor):
    Couple = apps.get_model("dates", "Couple")
    for couple in Couple.objects.all():
        members = list(couple.members.order_by("joined_at"))
        for member in members[1:]:
            member.is_planner = False
            member.reminders = False
            member.save(update_fields=["is_planner", "reminders"])


class Migration(migrations.Migration):

    dependencies = [
        ("dates", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="is_planner",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(mark_partners, migrations.RunPython.noop),
    ]
