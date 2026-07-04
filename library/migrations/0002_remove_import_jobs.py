from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ImportJobItem",
        ),
        migrations.DeleteModel(
            name="ImportJob",
        ),
    ]
