from django.db import migrations, models
from django.conf import settings


def set_main_profile_for_existing_users(apps, schema_editor):
    BusinessProfile = apps.get_model("accounts", "BusinessProfile")
    db_alias = schema_editor.connection.alias

    # For each user, ensure exactly one main profile is set.
    profiles = BusinessProfile.objects.using(db_alias).all().order_by("user_id", "created_at", "id")
    current_user_id = None
    main_set = False
    for profile in profiles:
        if profile.user_id != current_user_id:
            current_user_id = profile.user_id
            main_set = False
        if not main_set:
            profile.is_main = True
            main_set = True
        else:
            profile.is_main = False
        profile.save(update_fields=["is_main"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_googlebusinessprofileconnection_reviewsoverviewsnapshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businessprofile",
            name="user",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="business_profiles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="businessprofile",
            name="is_main",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(set_main_profile_for_existing_users, migrations.RunPython.noop),
    ]

