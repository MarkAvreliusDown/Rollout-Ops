import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0008_bonus_reconstructionrecord_salarysettings_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="Запись")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Когда")),
                (
                    "source",
                    models.CharField(
                        choices=[("web", "Сайт"), ("tg", "Telegram"), ("report", "Из старого отчёта")],
                        default="web",
                        max_length=10,
                        verbose_name="Источник",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="board.store",
                        verbose_name="Магазин",
                    ),
                ),
            ],
            options={
                "verbose_name": "Запись журнала",
                "verbose_name_plural": "Журнал",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="StoreLogFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="logs_files/%Y/%m/%d/", verbose_name="Файл")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружено")),
                (
                    "log",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="board.storelog",
                    ),
                ),
            ],
            options={
                "verbose_name": "Файл журнала",
                "verbose_name_plural": "Файлы журнала",
                "ordering": ["uploaded_at"],
            },
        ),
    ]
