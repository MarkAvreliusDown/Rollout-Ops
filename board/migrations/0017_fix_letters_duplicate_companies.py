# Исправление миграции 0016: там ошибочно решили, что вкладок SBER/Подрядчик 1/Подрядчик 2/
# Оборудование ещё нет, и создали для них новые пустые компании — хотя пользователь уже
# завёл их сам с реальными данными (под случайными ключами c_...). Эта миграция удаляет
# пустые дубли и вместо этого помечает автоподстановкой уже существующие настоящие вкладки.

from django.db import migrations

SOYUZ76_PRINTGRAD_TAGS = {
    "Филиал": "branch",
    "№ объекта": "number",
    "Адрес": "address",
    "Регион": "region",
    "Кол-во КСО": "kso_count",
    "Формат по площади": "area_format",
    "Кол-во колонок": "columns_count",
    "Тип колонок": "columns_type",
    "Дата СКС": "task_date:СКС",
    "Дата ПНР": "task_date:ПНР",
    "Дата ВПК-2": "task_date:ВПК-2",
    "Дата открытия": "task_date:Открытие",
}

SBER_TAGS = {
    "Филиал": "branch",
    "№ объекта": "number",
    "Адрес": "address",
    "Регион": "region",
    "кол-во ксо": "kso_count",
    "дата монтажа пинпадов": "task_date:Пинпады",
}

# У "оборудования" у пользователя часть столбцов называется иначе, чем в описании,
# и есть неоднозначные ("Формат", "Кол-во", "Кол-во колонок/тип") — их не трогаем,
# помечаем только то, что сопоставляется однозначно.
OBORUDOVANIE_TAGS = {
    "№ магазина": "number",
    "Адрес": "address",
    "Филиал": "branch",
    "Весы мясо": "has_meat_scale",
    "Кол-во точек доступа": "access_points_count",
    "Дата ПНР": "task_date:ПНР",
}


def fix_duplicates(apps, schema_editor):
    LetterCompany = apps.get_model("board", "LetterCompany")

    # Удаляем пустые дубли, которые ошибочно создала 0016.
    LetterCompany.objects.filter(
        key__in=["sber", "soyuz76", "printgrad", "oborudovanie"], rows=[],
    ).delete()

    def apply_tags(name, tags_map):
        company = LetterCompany.objects.filter(name=name).first()
        if not company:
            return
        changed = False
        for col in company.columns:
            tag = tags_map.get(col.get("name"))
            if tag and col.get("autofill") != tag:
                col["autofill"] = tag
                changed = True
        if not company.is_store_contractor:
            company.is_store_contractor = True
            changed = True
        if changed:
            company.save()

    apply_tags("SBER", SBER_TAGS)
    apply_tags("Подрядчик 1", SOYUZ76_PRINTGRAD_TAGS)
    apply_tags("Подрядчик 2", SOYUZ76_PRINTGRAD_TAGS)
    apply_tags("оборудование", OBORUDOVANIE_TAGS)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0016_letters_autofill_tags'),
    ]

    operations = [
        migrations.RunPython(fix_duplicates, noop_reverse),
    ]
