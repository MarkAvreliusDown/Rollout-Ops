import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0002_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="order",
            field=models.IntegerField(default=0, verbose_name="Порядок"),
        ),
        migrations.AddField(
            model_name="task",
            name="anchor_key",
            field=models.CharField(
                blank=True,
                choices=[("opening", "Открытие"), ("vpk2", "ВПК-2")],
                max_length=10,
                null=True,
                verbose_name="Ключ опорной даты",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="depends_on",
            field=models.CharField(
                blank=True,
                choices=[("opening", "Открытие"), ("vpk2", "ВПК-2")],
                max_length=10,
                null=True,
                verbose_name="Зависит от",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="offset_days",
            field=models.IntegerField(blank=True, null=True, verbose_name="Смещение (дней)"),
        ),
        migrations.AddField(
            model_name="task",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subtasks",
                to="board.task",
                verbose_name="Родительская задача",
            ),
        ),
        migrations.AlterModelOptions(
            name="task",
            options={"ordering": ["order", "id"], "verbose_name": "Задача", "verbose_name_plural": "Задачи"},
        ),
    ]
