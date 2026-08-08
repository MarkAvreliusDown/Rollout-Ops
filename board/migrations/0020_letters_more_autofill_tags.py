# Данные-миграция: добавляет теги автоподстановки для "Кол-во касс" (новое поле Store.cash_count)
# и для комбинированного столбца "оборудования" (кол-во колонок + тип), по просьбе пользователя.

from django.db import migrations

DASH = "‑"  # неразрывный дефис — именно так называется столбец у "оборудования"
OBORUDOVANIE_COMBINED_COLUMN = f"Кол{DASH}во колонок/тип"
OBORUDOVANIE_CASH_COLUMN = f"Кол{DASH}во касс"

CASH_COUNT_TARGETS = {
    "nv": "Кол-во касс",
    "c_1785161041203": "кол-во касс",       # SBER
    "c_1785161448434": "Кол-во касс",       # Подрядчик 1
    "c_1785161671679": "Кол-во касс",       # Подрядчик 2
}


def apply_tags(apps, schema_editor):
    LetterCompany = apps.get_model("board", "LetterCompany")

    for key, column_name in CASH_COUNT_TARGETS.items():
        company = LetterCompany.objects.filter(key=key).first()
        if not company:
            continue
        changed = False
        for col in company.columns:
            if col.get("name") == column_name and col.get("autofill") != "cash_count":
                col["autofill"] = "cash_count"
                changed = True
        if changed:
            company.save()

    oborudovanie = LetterCompany.objects.filter(key="c_1785219576608").first()
    if oborudovanie:
        changed = False
        for col in oborudovanie.columns:
            if col.get("name") == OBORUDOVANIE_CASH_COLUMN and col.get("autofill") != "cash_count":
                col["autofill"] = "cash_count"
                changed = True
            if col.get("name") == OBORUDOVANIE_COMBINED_COLUMN and col.get("autofill") != "columns_count_and_type":
                col["autofill"] = "columns_count_and_type"
                changed = True
        if changed:
            oborudovanie.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0019_store_cash_count_alter_store_area_format'),
    ]

    operations = [
        migrations.RunPython(apply_tags, noop_reverse),
    ]
