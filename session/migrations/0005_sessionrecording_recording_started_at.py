from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('session', '0004_add_status_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionrecording',
            name='recording_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
