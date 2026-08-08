import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0009_storelog"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelegramSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chat_id", models.CharField(max_length=50, unique=True, verbose_name="Chat ID")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                (
                    "store",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tg_sessions",
                        to="board.store",
                        verbose_name="Выбранный объект",
                    ),
                ),
            ],
            options={
                "verbose_name": "Сессия Telegram",
                "verbose_name_plural": "Сессии Telegram",
            },
        ),
    ]
