from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0003_catalogtag_slug"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="book",
            name="source_filename",
        ),
    ]
