from django.core.management.base import BaseCommand

from board.views import _build_today_digest, send_telegram_message


class Command(BaseCommand):
    help = "Отправляет список сегодняшних задач в Telegram (для запуска по расписанию)"

    def handle(self, *args, **options):
        text = _build_today_digest()
        try:
            send_telegram_message(text)
            self.stdout.write(self.style.SUCCESS("Отправлено в Telegram"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка: {e}"))
