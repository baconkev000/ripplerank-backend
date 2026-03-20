from django.db import migrations, models


def migrate_global_to_local(apps, schema_editor):
    BusinessProfile = apps.get_model("accounts", "BusinessProfile")
    BusinessProfile.objects.filter(seo_location_mode="global").update(seo_location_mode="local")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0028_businessprofile_seo_location_mode"),
    ]

    operations = [
        migrations.RunPython(migrate_global_to_local, noop_reverse),
        migrations.AlterField(
            model_name="businessprofile",
            name="seo_location_mode",
            field=models.CharField(
                choices=[("organic", "Organic"), ("local", "Local")],
                default="organic",
                max_length=16,
            ),
        ),
    ]
