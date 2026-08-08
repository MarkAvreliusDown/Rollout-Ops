from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0005_archive_notedate"),
    ]

    operations = [
        migrations.RenameField(
            model_name="reportphoto",
            old_name="image",
            new_name="file",
        ),
        migrations.AlterField(
            model_name="reportphoto",
            name="file",
            field=models.FileField(upload_to="reports/%Y/%m/%d/", verbose_name="Файл"),
        ),
        migrations.AlterModelOptions(
            name="reportphoto",
            options={"ordering": ["uploaded_at"], "verbose_name": "Файл отчёта", "verbose_name_plural": "Файлы отчётов"},
        ),
    ]
