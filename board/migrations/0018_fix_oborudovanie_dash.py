# Досогласование 0017: столбец "Кол-во точек доступа" в вкладке "оборудование" на самом
# деле называется с неразрывным дефисом (U+2011, "Кол‑во точек доступа"), а не обычным
# "-" — из-за этого тег автоподстановки на него не наложился. Поправляем точечно.

from django.db import migrations

DASH = "‑"  # неразрывный дефис
COLUMN_NAME = f"Кол{DASH}во точек доступа"


def fix_column(apps, schema_editor):
    LetterCompany = apps.get_model("board", "LetterCompany")
    company = LetterCompany.objects.filter(key="c_1785219576608").first()
    if not company:
        return
    changed = False
    for col in company.columns:
        if col.get("name") == COLUMN_NAME and col.get("autofill") != "access_points_count":
            col["autofill"] = "access_points_count"
            changed = True
    if changed:
        company.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0017_fix_letters_duplicate_companies'),
    ]

    operations = [
        migrations.RunPython(fix_column, noop_reverse),
    ]
