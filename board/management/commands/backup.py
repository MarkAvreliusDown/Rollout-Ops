"""
Резервное копирование базы данных и файлов (медиа) в один ZIP-архив.

Что попадает в архив:
  - db.sqlite3 (вся база — магазины, задачи, журналы, база знаний и т.д.),
  - папка media/ (фотографии, документы, вложения).

Секреты (.env) в архив НЕ попадают — это сделано намеренно, чтобы бэкапы
можно было безопасно хранить/копировать куда угодно.

Куда сохраняется: C:\\mybacks\\backup_ГГГГ-ММ-ДД_ЧЧММ.zip
(папка создаётся автоматически, если её ещё нет).

Запуск вручную:
    python manage.py backup
(или двойной клик по backup.bat в корне проекта)

Автоматический запуск каждый день в 10:00 настраивается один раз через
setup_backup_task.bat (создаёт задание в Планировщике заданий Windows).
"""

import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

BACKUP_DIR = Path(r"C:\mybacks")


class Command(BaseCommand):
    help = "Делает ZIP-бэкап базы данных и папки media в C:\\mybacks"

    def handle(self, *args, **options):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        stamp = timezone.now().strftime("%Y-%m-%d_%H%M")
        zip_path = BACKUP_DIR / f"backup_{stamp}.zip"

        db_path = settings.BASE_DIR / "db.sqlite3"
        media_root = Path(settings.MEDIA_ROOT)

        files_count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if db_path.exists():
                zf.write(db_path, arcname="db.sqlite3")
                files_count += 1

            if media_root.exists():
                for file_path in media_root.rglob("*"):
                    if file_path.is_file():
                        arcname = str(Path("media") / file_path.relative_to(media_root))
                        zf.write(file_path, arcname=arcname)
                        files_count += 1

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(
            f"Бэкап готов: {zip_path}  ({size_mb:.1f} МБ, файлов внутри: {files_count})"
        ))
