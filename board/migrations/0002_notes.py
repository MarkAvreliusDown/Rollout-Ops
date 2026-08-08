import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="store",
            name="store_type",
            field=models.CharField(
                choices=[
                    ("opening", "Открытие"),
                    ("reconstruction", "Реконструкция"),
                    ("extra", "Доп. работы"),
                ],
                max_length=20,
                verbose_name="Тип",
            ),
        ),
        migrations.CreateModel(
            name="Note",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="Текст заметки")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="board.task",
                    ),
                ),
            ],
            options={
                "verbose_name": "Заметка",
                "verbose_name_plural": "Заметки",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="NoteFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="notes/%Y/%m/%d/", verbose_name="Файл")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружено")),
                (
                    "note",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="board.note",
                    ),
                ),
            ],
            options={
                "verbose_name": "Файл заметки",
                "verbose_name_plural": "Файлы заметок",
                "ordering": ["uploaded_at"],
            },
        ),
    ]
