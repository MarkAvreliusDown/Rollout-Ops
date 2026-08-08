from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0011_task_icon"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramsession",
            name="mode",
            field=models.CharField(default="log", max_length=20, verbose_name="Режим"),
        ),
        migrations.AddField(
            model_name="note",
            name="source",
            field=models.CharField(default="web", max_length=10, verbose_name="Источник"),
        ),
    ]
