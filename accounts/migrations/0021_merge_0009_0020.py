from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_businessprofile_multiple_and_is_main"),
        ("accounts", "0020_seooverviewsnapshot_keyword_action_suggestions"),
    ]

    operations = [
        # This is a merge migration to resolve multiple leaf nodes (0009 and 0020).
        # No schema changes are required here.
    ]

