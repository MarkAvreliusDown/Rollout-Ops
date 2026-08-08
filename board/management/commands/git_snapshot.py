"""
Снимок всего проекта в локальный git-репозиторий (версионирование).

Что попадает в снимок: весь проект целиком, включая db.sqlite3 (боевая база)
и папку media/ (фотографии, документы, вложения) — чтобы откат к любому
снимку разом восстанавливал код, базу и медиа вместе.

Секреты (.env) в снимок НЕ попадают — файл в .gitignore, коммитится только
то, что не исключено .gitignore.

Команда делает `git add -A` и `git commit` с автоматическим сообщением
вида "Снимок 2026-08-08 10:00". Если изменений с прошлого снимка нет —
это не ошибка, коммит просто не создаётся.

Предполагается, что git-репозиторий в корне проекта уже проинициализирован
(`git init` здесь не выполняется).

Запуск вручную:
    python manage.py git_snapshot
"""

import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Делает снимок всего проекта (код + db.sqlite3 + media) в локальный git"

    def handle(self, *args, **options):
        try:
            add_result = subprocess.run(
                ["git", "add", "-A"],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(
                "Git не найден. Установите Git для Windows (https://git-scm.com/download/win) "
                "и убедитесь, что он добавлен в PATH."
            ))
            return

        if add_result.returncode != 0:
            self.stderr.write(self.style.ERROR(
                f"Не удалось выполнить git add -A: {add_result.stderr.strip()}"
            ))
            return

        stamp = timezone.now().strftime("%Y-%m-%d %H:%M")
        commit_result = subprocess.run(
            ["git", "commit", "-m", f"Снимок {stamp}"],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
        )

        if commit_result.returncode == 0:
            self.stdout.write(self.style.SUCCESS(f"Снимок сделан: {stamp}"))
            return

        output = (commit_result.stdout or "") + (commit_result.stderr or "")
        if "nothing to commit" in output.lower():
            self.stdout.write(self.style.SUCCESS("Изменений нет, снимок не нужен"))
            return

        self.stderr.write(self.style.ERROR(
            f"Не удалось сделать снимок: {output.strip()}"
        ))
