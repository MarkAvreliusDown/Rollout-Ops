
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

SECRET_KEY = "django-insecure-local-only-change-me-if-you-ever-deploy-this"

# Локальный инструмент для одного человека — DEBUG включён специально.
DEBUG = True

ALLOWED_HOSTS = ["*"]  # локальный инструмент, доступ только внутри домашней/офисной сети

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "board",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "board.middleware.SitePasswordMiddleware",
    "board.middleware.NoBrowserCacheMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cf_board.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cf_board.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Пароль на весь сайт (простая защита, без логинов/пользователей).
# Если оставить пустым в .env — сайт останется полностью открытым, как раньше.
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "")

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Сайт (start_server.bat) и telegram-бот (start_bot.bat) — два разных процесса,
# которые живут постоянно и запускаются/перезапускаются независимо друг от друга.
# Если оба пишут в один файл ai.log, то ровно в полночь при архивации файла один
# процесс держит его открытым, пока второй пытается переименовать — Windows это
# запрещает (PermissionError). Поэтому у бота — свой отдельный файл лога.
LOG_FILENAME = "bot.log" if "telegram_bot" in sys.argv else "ai.log"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s [%(levelname)s] %(message)s", "datefmt": "%d.%m.%Y %H:%M:%S"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            # Переворачивается каждую полночь в отдельный файл (ai.log.2026-08-02 и т.п.),
            # хранится 6 дней, старые файлы удаляются автоматически.
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": str(LOGS_DIR / LOG_FILENAME),
            "when": "midnight",
            "backupCount": 6,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "board": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
    },
}


