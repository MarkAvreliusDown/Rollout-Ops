#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cf_board.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не удалось импортировать Django. Убедись, что виртуальное окружение "
            "активировано и зависимости установлены (pip install -r requirements.txt)."
        ) from exc
    execute_from_command_line(sys.argv)
