from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0012_quicknotes"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="due_time",
            field=models.TimeField(blank=True, null=True, verbose_name="Время"),
        ),
        migrations.AddField(
            model_name="task",
            name="notified_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Уведомление отправлено"),
        ),
    ]
