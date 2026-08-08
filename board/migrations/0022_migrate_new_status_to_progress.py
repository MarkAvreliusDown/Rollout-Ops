# Убрали статус "Новое" по просьбе пользователя — теперь начальный статус "В работе".
# Переносим существующие задачи со старым статусом "new" на "progress".

from django.db import migrations


def migrate_status(apps, schema_editor):
    Task = apps.get_model("board", "Task")
    Task.objects.filter(status="new").update(status="progress")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0021_alter_task_status'),
    ]

    operations = [
        migrations.RunPython(migrate_status, noop_reverse),
    ]
