import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0003_task_order_subtasks_dates"),
    ]

    operations = [
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, verbose_name="Имя")),
                ("role", models.CharField(blank=True, max_length=150, verbose_name="Роль / компания")),
                ("phone", models.CharField(blank=True, max_length=50, verbose_name="Телефон")),
                ("telegram", models.CharField(blank=True, max_length=100, verbose_name="Telegram (username)")),
                ("max_contact", models.CharField(blank=True, max_length=100, verbose_name="MAX (username)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="board.store",
                    ),
                ),
            ],
            options={
                "verbose_name": "Контакт",
                "verbose_name_plural": "Контакты",
                "ordering": ["name"],
            },
        ),
    ]
