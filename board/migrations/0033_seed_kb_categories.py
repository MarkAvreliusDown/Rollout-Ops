from django.db import migrations

CATEGORIES = [
    {"name": "Кассы", "image": "kb_categories/icon_kassy.png", "image_has_caption": True, "order": 1},
    {"name": "Офисное оборудование", "image": "kb_categories/icon_office.png", "image_has_caption": True, "order": 2},
    {"name": "Формы запросов", "image": "kb_categories/icon_forms.png", "image_has_caption": True, "order": 3},
    {"name": "Образы", "image": "kb_categories/icon_obrazy.svg", "image_has_caption": True, "order": 4},
]


def seed_categories(apps, schema_editor):
    KbCategory = apps.get_model("board", "KbCategory")
    for data in CATEGORIES:
        KbCategory.objects.get_or_create(name=data["name"], defaults=data)


def remove_categories(apps, schema_editor):
    KbCategory = apps.get_model("board", "KbCategory")
    names = [data["name"] for data in CATEGORIES]
    KbCategory.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0032_kbcategory_article_category'),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
