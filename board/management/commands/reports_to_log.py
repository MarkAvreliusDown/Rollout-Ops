"""
Разовый перенос старых отчётов (Report) в журнал по объекту (StoreLog).

Что делает:
  - берёт каждый отчёт, у которого есть текст (черновик или итоговый) либо файлы,
  - создаёт запись в журнале того же магазина с ТОЙ ЖЕ датой и временем,
  - привязывает к записи все файлы/фото этого отчёта (файлы на диске не трогаются
    и не копируются — просто появляется вторая ссылка на них),
  - сами отчёты НЕ удаляет и НЕ изменяет.

Команду можно запускать повторно — уже перенесённые отчёты пропускаются.

Запуск:
    python manage.py reports_to_log --dry-run   # только посмотреть, что будет
    python manage.py reports_to_log             # выполнить перенос
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Report, StoreLog, StoreLogFile


class Command(BaseCommand):
    help = "Переносит тексты и файлы старых отчётов в журнал по объекту"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ничего не записывать в базу, только показать план",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        reports = (
            Report.objects.select_related("store")
            .prefetch_related("photos")
            .order_by("created_at")
        )

        moved = 0
        skipped_empty = 0
        skipped_done = 0
        files_moved = 0

        for report in reports:
            text = (report.draft_text or "").strip()
            if not text:
                text = (report.final_text or "").strip()

            photos = [p for p in report.photos.all() if p.file]

            if not text and not photos:
                skipped_empty += 1
                continue

            already = StoreLog.objects.filter(
                store_id=report.store_id,
                created_at=report.created_at,
                source="report",
            ).exists()
            if already:
                skipped_done += 1
                continue

            preview = text[:50].replace("\n", " ") if text else "(без текста)"
            label = f"[{report.store.number}] {report.created_at:%d.%m.%Y %H:%M} — {preview}"

            if dry_run:
                self.stdout.write(f"  перенесу: {label}  (файлов: {len(photos)})")
                moved += 1
                files_moved += len(photos)
                continue

            with transaction.atomic():
                log = StoreLog.objects.create(
                    store_id=report.store_id,
                    text=text or "(запись без текста, только файлы)",
                    source="report",
                )
                # created_at объявлено с default=timezone.now, поэтому исходную дату
                # проставляем отдельным update — иначе запись получит сегодняшнее число.
                StoreLog.objects.filter(pk=log.pk).update(created_at=report.created_at)

                for photo in photos:
                    log_file = StoreLogFile(log=log)
                    log_file.file.name = photo.file.name
                    log_file.save()
                    files_moved += 1

            moved += 1
            self.stdout.write(f"  ок: {label}")

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ПРОСМОТРА — в базу ничего не записано."))
        self.stdout.write(self.style.SUCCESS(f"Перенесено записей:  {moved}"))
        self.stdout.write(f"Привязано файлов:    {files_moved}")
        self.stdout.write(f"Пропущено пустых:    {skipped_empty}")
        self.stdout.write(f"Уже было перенесено: {skipped_done}")
