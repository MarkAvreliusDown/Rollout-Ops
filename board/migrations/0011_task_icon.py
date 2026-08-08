from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0010_telegramsession"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="icon_name",
            field=models.CharField(blank=True, max_length=30, verbose_name="Иконка"),
        ),
        migrations.AddField(
            model_name="task",
            name="icon_color",
            field=models.CharField(blank=True, max_length=10, verbose_name="Цвет иконки"),
        ),
    ]
