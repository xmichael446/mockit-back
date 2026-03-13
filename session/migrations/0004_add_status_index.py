from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('session', '0003_sessionrecording'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ieltsmocksession',
            name='status',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'Scheduled'), (2, 'In Progress'), (3, 'Completed'), (4, 'Cancelled')],
                db_index=True,
                default=1,
            ),
        ),
    ]
