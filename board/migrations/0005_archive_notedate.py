from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0004_contact"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="В архиве"),
        ),
        migrations.AddField(
            model_name="note",
            name="due_date",
            field=models.DateField(blank=True, null=True, verbose_name="Дата"),
        ),
    ]
