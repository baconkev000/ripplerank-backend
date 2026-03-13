from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_metaadsconnection"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofile",
            name="plan",
            field=models.CharField(max_length=64, blank=True),
        ),
    ]

