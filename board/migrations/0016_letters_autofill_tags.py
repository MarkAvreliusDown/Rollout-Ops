# Данные-миграция: помечает существующие столбцы писем (провайдер 2/Подрядчик 3/НВ)
# тегами автоподстановки и заводит новые вкладки Банк-эквайер/Подрядчик 1/
# Подрядчик 2/Оборудование — по описанию, которое дал пользователь. Существующие
# строки (rows) не трогает.

from django.db import migrations

Provider2_TAGS = {
    "Филиал": "branch",
    "№ объекта": "number",
    "Адрес": "address",
    "Регион": "region",
    "Дата монтажа резервного канала": "task_date:Резервный канал",
}

SERVPLUS_TAGS = {
    "Филиал": "branch",
    "№ объекта": "number",
    "Адрес": "address",
    "Регион": "region",
    "Кол-во КСО": "kso_count",
    "ПНР КСО": "task_date:ПНР КСО",
    "Монтаж тумб": "task_date:Монтаж тумб",
}

NV_TAGS = {
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

NV_LIKE_COLUMNS = [
    {"name": "Филиал", "autofill": "branch"},
    {"name": "№ объекта", "autofill": "number"},
    {"name": "Адрес", "autofill": "address"},
    {"name": "Регион", "autofill": "region"},
    {"name": "Кол-во касс", "autofill": None},
    {"name": "Кол-во КСО", "autofill": "kso_count"},
    {"name": "Формат по площади", "autofill": "area_format"},
    {"name": "Кол-во колонок", "autofill": "columns_count"},
    {"name": "Тип колонок", "autofill": "columns_type"},
    {"name": "TUNIP", "autofill": None},
    {"name": "Внутренние IP адреса", "autofill": None},
    {"name": "Дата СКС", "autofill": "task_date:СКС"},
    {"name": "Дата ПНР", "autofill": "task_date:ПНР"},
    {"name": "Дата ВПК-2", "autofill": "task_date:ВПК-2"},
    {"name": "Дата открытия", "autofill": "task_date:Открытие"},
    {"name": "Подрядчик СКС", "autofill": None},
    {"name": "Подрядчик ПНР", "autofill": None},
]

SBER_COLUMNS = [
    {"name": "Филиал", "autofill": "branch"},
    {"name": "№ объекта", "autofill": "number"},
    {"name": "Адрес", "autofill": "address"},
    {"name": "Регион", "autofill": "region"},
]

OBORUDOVANIE_COLUMNS = [
    {"name": "Филиал", "autofill": "branch"},
    {"name": "№ объекта", "autofill": "number"},
    {"name": "Адрес", "autofill": "address"},
    {"name": "Регион", "autofill": "region"},
    {"name": "Весы мясо", "autofill": "has_meat_scale"},
    {"name": "Кол-во точек доступа", "autofill": "access_points_count"},
    {"name": "Крайний срок доставки", "autofill": None},
    {"name": "Дата ПНР", "autofill": "task_date:ПНР"},
    {"name": "Доп инфо", "autofill": None},
]


def tag_and_seed(apps, schema_editor):
    LetterCompany = apps.get_model("board", "LetterCompany")

    def apply_tags(key, tags_map):
        try:
            company = LetterCompany.objects.get(key=key)
        except LetterCompany.DoesNotExist:
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

    apply_tags("provider2", Provider2_TAGS)
    apply_tags("servplus", SERVPLUS_TAGS)
    apply_tags("nv", NV_TAGS)

    def create_if_missing(key, name, columns, order):
        if LetterCompany.objects.filter(key=key).exists():
            return
        LetterCompany.objects.create(
            key=key, name=name, order=order, header="Филиал 3", subject=f"График работ — {name}",
            recipients="", columns=columns, rows=[], is_store_contractor=True,
        )

    create_if_missing("sber", "Банк-эквайер", SBER_COLUMNS, 100)
    create_if_missing("soyuz76", "Подрядчик 1", NV_LIKE_COLUMNS, 101)
    create_if_missing("printgrad", "Подрядчик 2", NV_LIKE_COLUMNS, 102)
    create_if_missing("oborudovanie", "Оборудование", OBORUDOVANIE_COLUMNS, 103)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0015_lettercompany_is_store_contractor_and_more'),
    ]

    operations = [
        migrations.RunPython(tag_and_seed, noop_reverse),
    ]
