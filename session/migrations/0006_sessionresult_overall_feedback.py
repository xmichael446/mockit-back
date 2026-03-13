from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('session', '0005_sessionrecording_recording_started_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionresult',
            name='overall_feedback',
            field=models.TextField(blank=True, null=True),
        ),
    ]
