import uuid

from django.db import migrations, models


def backfill_keys(apps, schema_editor):
    Contractor = apps.get_model('board', 'Contractor')
    for c in Contractor.objects.all():
        c.key = uuid.uuid4().hex
        c.save(update_fields=['key'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0026_budgetsettings_contractor_budgetcalculation'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractor',
            name='key',
            field=models.CharField(default='', max_length=64, verbose_name='Ключ'),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_keys, noop_reverse),
        migrations.AlterField(
            model_name='contractor',
            name='key',
            field=models.CharField(max_length=64, unique=True, verbose_name='Ключ'),
        ),
    ]
