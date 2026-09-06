from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_browserloginthrottleslot")]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="web_session_generation",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
    ]
