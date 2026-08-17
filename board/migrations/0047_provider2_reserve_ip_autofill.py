# Данные-миграция: помечает столбец "Внешние IP резервного канала" у письма
# Provider2 тегом автоподстановки wan_ip2_reserve. Существующие rows не трогает.

from django.db import migrations

COLUMN_NAME = "Внешние IP резервного канала"
AUTOFILL_TAG = "wan_ip2_reserve"


def tag_column(apps, schema_editor):
    LetterCompany = apps.get_model("board", "LetterCompany")
    try:
        company = LetterCompany.objects.get(key="provider2")
    except LetterCompany.DoesNotExist:
        return
    changed = False
    for col in company.columns:
        if col.get("name") == COLUMN_NAME and col.get("autofill") != AUTOFILL_TAG:
            col["autofill"] = AUTOFILL_TAG
            changed = True
    if changed:
        company.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0046_notification'),
    ]

    operations = [
        migrations.RunPython(tag_column, noop_reverse),
    ]
