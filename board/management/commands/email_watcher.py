"""
Почтовый ассистент — постоянно проверяет рабочую почту (Exchange/Office 365,
обычная логин/пароль авторизация, БЕЗ OAuth) и создаёт заметку на дашборде,
когда приходит письмо с просьбой, связанной с бюджетом — предоставить/направить/
рассчитать бюджет (по подразделениям, реконструкции, объекта и т.п.)
(или похожее по смыслу).

Запуск (в ОТДЕЛЬНОМ окне, сайт/бот/голосовой ассистент при этом работают
как обычно):
    python manage.py email_watcher

Остановить — Ctrl+C.

Что нужно в .env:
    EMAIL_ADDRESS  — рабочий email (он же логин, если не задан EMAIL_USERNAME)
    EMAIL_PASSWORD — пароль от почты
    EMAIL_USERNAME — необязательно, логин для входа на сервер, если он
                     отличается от email (например DOMAIN\\username для
                     локального корпоративного Exchange); если не задан —
                     используется EMAIL_ADDRESS как логин
    EMAIL_SERVER   — необязательно, адрес сервера Exchange (например
                     mail.company.ru); если не задан — используется
                     autodiscover (exchangelib сам найдёт сервер по email)
    EMAIL_POLL_INTERVAL — необязательно, как часто проверять почту в секундах
                     (по умолчанию 300 — раз в 5 минут)

Как работает:
    Раз в EMAIL_POLL_INTERVAL секунд подключается к папке "Входящие" через
    exchangelib и смотрит письма за последние 14 дней (не весь ящик — иначе
    на большом ящике каждая проверка была бы долгой). Для каждого письма,
    которое ещё не обработано (ProcessedEmail.message_id), проверяет
    ключевые слова-триггеры (см. TRIGGER_KEYWORDS ниже) в теме и тексте.
    Если совпало — отправляет текст письма в локальную Ollama с просьбой
    определить, действительно ли это просьба, связанная с бюджетом, и достать
    из письма срок. Если Ollama подтвердила — создаёт Note (заметку на
    дашборде, source="email") и переносит в неё все файловые вложения письма
    (NoteFile) как есть — если вложений нет, заметка создаётся без файлов.
    В любом случае письмо помечается обработанным (ProcessedEmail), чтобы не
    проверять его повторно.

Письма про КПП магазина (отдельная ветка, без ИИ):
    Если в теме или тексте письма встречается слово «кпп» (без учёта
    регистра, как отдельное слово) — это отдельный сценарий, никак не
    связанный с бюджетными письмами выше. Все файловые вложения такого
    письма сохраняются как есть (под тем же именем файла, что было в
    письме) сразу в обе папки на Яндекс.Диске:
        C:\\Users\\<username>\\Yandex.Disk\\КСО\\кпп
        C:\\Users\\<username>\\Yandex.Disk\\пнр\\кпп
    (см. KPP_TARGET_DIRS — поправь пути под свою учётную запись и структуру
    папок). Никакого обращения к Ollama и никакой Note при
    этом не создаётся — письмо просто помечается обработанным. Если в
    папке уже есть файл с таким именем, он не перезаписывается — новый
    файл получает суффикс " (2)", " (3)" и т.д. перед расширением. Если у
    письма со словом «кпп» вообще нет вложений — ничего не сохраняется,
    в лог пишется предупреждение. Во время копирования в консоли
    отдельного окна email_watcher видна прогресс-шкала (обновляется на
    месте через \\r) и построчный отчёт о каждом сохранённом файле
    (имя и путь назначения); ошибка сохранения одного файла в одну из
    папок не прерывает копирование остальных — пишется в консоль и в лог,
    и цикл продолжается.

Письма от банка-эквайера о закрытии обращения в поддержку (отдельная
ветка, без ИИ):
    Если письмо от отправителя, чей email/имя совпадает с шаблоном
    ACQUIRER_SENDER_RE (настраивается под конкретного банка-эквайера),
    и в тексте письма встречается фраза-маркер закрытия обращения — создаётся
    Notification (уведомление для колокольчика на сайте), Ollama при этом не
    вызывается. Письмо всё равно помечается обработанным.

Письма от интернет-провайдера о монтаже нового канала связи (отдельная
ветка, без ИИ):
    Если письмо от отправителя с адресом на домене провайдера (конкретный
    адрес технической поддержки у провайдеров обычно плавающий — разные
    отправители с одного домена, поэтому проверяется домен, а не один
    фиксированный адрес) и тема письма содержит фразу-маркер монтажа канала
    — создаётся Notification (уведомление для колокольчика на сайте), Ollama
    при этом не вызывается. Письмо всё равно помечается обработанным.

Всё работает локально: единственное обращение "наружу" — сам запрос к
почтовому серверу компании (это неизбежно, иначе почту не прочитать).
Разбор текста письма — через локальную Ollama, как везде в проекте,
никуда в интернет не уходит.

Известные ограничения:
    - Только логин/пароль (Basic/NTLM через exchangelib), без OAuth — если
      у почтового сервера OAuth обязателен, эта команда не подключится.
    - Проверяются только последние 14 дней и не больше 50 писем за один
      проход — расширить период/лимит можно, поправив EMAIL_LOOKBACK_DAYS
      и срез [:50] ниже в файле.
    - Список ключевых слов-триггеров — фиксированный список в начале файла
      (TRIGGER_KEYWORDS), дополнять вручную по мере необходимости.
    - Если Ollama не смогла разобрать письмо (упала, вернула не-JSON) —
      письмо просто помечается обработанным без создания заметки, ничего
      не падает.
    - Папки для вложений КПП (KPP_TARGET_DIRS) — фиксированный список путей
      в начале файла, менять вручную при необходимости.
"""

import datetime
import json
import logging
import os
import re
import sys
import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from board.models import Note, NoteFile, Notification, ProcessedEmail
from board.views import _call_llm

logger = logging.getLogger("board")

# Ключевые слова-триггеры (нижний регистр, ищутся по вхождению в теме+теле письма,
# без учёта регистра). Дополняйте список, если появляются новые формулировки просьб.
TRIGGER_KEYWORDS = [
    "бюджет",
    "просьба предоставить",
    "просьба направить",
    "прошу направить",
    "прошу предоставить",
]

# Куда сохранять вложения писем про КПП магазина (в обе папки сразу).
# Пути ниже — пример, поправь под свою учётную запись Windows и структуру папок.
KPP_TARGET_DIRS = [
    r"C:\Users\<username>\Yandex.Disk\КСО\кпп",
    r"C:\Users\<username>\Yandex.Disk\пнр\кпп",
]

KPP_WORD_RE = re.compile(r"\bкпп\b", re.IGNORECASE)

# Письма от банка-эквайера о закрытии обращения в поддержку — отдельная
# ветка без Ollama, создаёт Notification для колокольчика на сайте.
# Значения ниже — пример, подставь реальные под своего банка-эквайера.
ACQUIRER_SUPPORT_DONE_TEXT = "Ваше обращение в службу поддержки эквайринга выполнено."
ACQUIRER_SENDER_RE = re.compile(r"acquirer-example", re.IGNORECASE)

# Письма от интернет-провайдера о монтаже нового канала связи — тоже
# отдельная ветка без Ollama, создаёт Notification для колокольчика на сайте.
# Проверяется домен отправителя, не конкретный адрес — техподдержка обычно
# пишет с разных адресов одного домена. Значения ниже — пример, подставь
# домен и тему реального провайдера.
ISP_SENDER_DOMAIN = "@isp-example.ru"
# Некоторые письма могут приходить с визуально неотличимой латинской буквой
# вместо кириллической в начале темы (например латинская "C" вместо
# кириллической "С") — это ломает точное совпадение подстроки, поэтому
# сравнение ниже сделано без первой буквы темы-маркера.
ISP_CHANNEL_SUBJECT = "монтирован новый канал связи"

# Сколько дней письма проверяем за один проход (не гоняем весь ящик).
EMAIL_LOOKBACK_DAYS = 14
EMAIL_BATCH_LIMIT = 50

INTENT_PROMPT = """Ты — модуль разбора рабочих писем. Тебе дано письмо (тема и текст).
Определи, является ли это письмо просьбой, связанной с бюджетом — предоставить/направить/
рассчитать бюджет (например: бюджет по подразделениям, бюджет реконструкции, бюджет объекта,
смета/расчёт стоимости работ) — или похожей по смыслу просьбой прислать какой-то отчёт/данные
к определённому сроку.

Верни СТРОГО один JSON-объект без пояснений, без markdown, без ```. Формат:
{{"is_relevant": true/false, "due_date": "YYYY-MM-DD" или null, "due_time": "HH:MM" или null, "summary": "краткое описание на русском"}}

due_date/due_time — срок, к которому нужно предоставить данные, если он указан в письме
(сегодняшняя дата: {today}). Если срок не указан — null. Если письмо не по теме — is_relevant: false.

Тема письма: "{subject}"
Текст письма:
{body}
"""


def _contains_trigger(subject, body):
    haystack = f"{subject}\n{body}".lower()
    return any(kw in haystack for kw in TRIGGER_KEYWORDS)


def _contains_kpp(subject, body):
    haystack = f"{subject}\n{body}"
    return bool(KPP_WORD_RE.search(haystack))


def _is_acquirer_sender(msg):
    """msg.sender — объект exchangelib Mailbox (email_address/name), может
    быть None у некоторых писем."""
    sender = getattr(msg, "sender", None)
    if sender is None:
        return False
    email_address = getattr(sender, "email_address", None) or ""
    if ACQUIRER_SENDER_RE.search(email_address):
        return True
    name = getattr(sender, "name", None) or ""
    return bool(ACQUIRER_SENDER_RE.search(name))


def _contains_acquirer_support_done(subject, body):
    return ACQUIRER_SUPPORT_DONE_TEXT in body


def _is_isp_sender(msg):
    sender = getattr(msg, "sender", None)
    if sender is None:
        return False
    email_address = getattr(sender, "email_address", None) or ""
    return email_address.strip().lower().endswith(ISP_SENDER_DOMAIN)


def _contains_isp_channel_subject(subject):
    return ISP_CHANNEL_SUBJECT.lower() in (subject or "").lower()


def _safe_attachment_name(name):
    """Очищает имя вложения от разделителей пути и управляющих символов —
    имя приходит из внешнего письма, доверять ему нельзя (path traversal)."""
    name = os.path.basename(name or "")
    name = re.sub(r"[\x00-\x1f]", "", name)
    name = name.strip().strip(".")
    return name or "attachment"


def _unique_path(target_dir, filename):
    """Если файл с таким именем уже есть — подбирает имя с суффиксом
    " (2)", " (3)" и т.д. перед расширением, чтобы не перезаписать."""
    base, ext = os.path.splitext(filename)
    candidate = filename
    n = 2
    while os.path.exists(os.path.join(target_dir, candidate)):
        candidate = f"{base} ({n}){ext}"
        n += 1
    return os.path.join(target_dir, candidate)


def _print_progress_bar(current, total, label):
    """Печатает прогресс-шкалу в консоль отдельного окна email_watcher,
    обновляя её на месте через \\r вместо новой строки на каждый шаг."""
    if total <= 0:
        return
    width = 30
    ratio = min(max(current / total, 0), 1)
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    percent = int(ratio * 100)
    sys.stdout.write(f"\r{label}: [{bar}] {percent}% ({current}/{total})")
    if current >= total:
        sys.stdout.write("\n")
    sys.stdout.flush()


def _get_file_attachments(msg):
    """Возвращает файловые вложения письма (не inline, с содержимым) —
    общий хелпер для веток КПП и бюджетных писем."""
    from exchangelib.attachments import FileAttachment

    return [
        a for a in (msg.attachments or [])
        if isinstance(a, FileAttachment) and not a.is_inline and a.content
    ]


def _save_kpp_attachments(msg):
    """Сохраняет все файловые вложения письма в обе папки KPP_TARGET_DIRS
    под оригинальным именем (без перезаписи существующих файлов).
    Возвращает True, если хоть один файл сохранён."""
    attachments = _get_file_attachments(msg)
    if not attachments:
        logger.warning("Почтовый ассистент: письмо про КПП без вложений — %s", (msg.subject or "")[:100])
        return False

    subject = (msg.subject or "")[:80]
    sys.stdout.write(f"Копирование вложений КПП из письма «{subject}»...\n")
    sys.stdout.flush()

    total_steps = len(attachments) * len(KPP_TARGET_DIRS)
    step = 0

    saved_any = False
    for attachment in attachments:
        filename = _safe_attachment_name(attachment.name)
        for target_dir in KPP_TARGET_DIRS:
            step += 1
            _print_progress_bar(step, total_steps, "Копирование КПП")
            try:
                os.makedirs(target_dir, exist_ok=True)
                path = _unique_path(target_dir, filename)
                with open(path, "wb") as f:
                    f.write(attachment.content)
            except Exception as e:
                logger.exception(
                    "Почтовый ассистент: не удалось сохранить вложение КПП %s в %s",
                    filename, target_dir,
                )
                sys.stdout.write(f"  Ошибка копирования {filename} в {target_dir}: {e}\n")
                sys.stdout.flush()
                continue
            saved_any = True
            sys.stdout.write(f"  Скопировано: {filename} -> {path}\n")
            sys.stdout.flush()
            logger.info("Почтовый ассистент: вложение КПП сохранено — %s", path)
    return saved_any


def _call_llm_intent(subject, body):
    """Возвращает dict {is_relevant, due_date, due_time, summary} или None,
    если разобрать не удалось (сеть/Ollama недоступна, не-JSON ответ и т.п.)."""
    prompt = INTENT_PROMPT.format(
        today=datetime.date.today().isoformat(),
        subject=subject[:300],
        body=body[:4000],
    )
    try:
        resp = _call_llm(prompt, timeout=120)
        data_raw = resp.json()
        candidates = data_raw.get("candidates") or []
        if not candidates:
            logger.warning("Почтовый ассистент: Ollama вернула ошибку вместо ответа: %s", data_raw)
            return None
        answer = candidates[0]["content"]["parts"][0]["text"].strip()
    except Exception:
        logger.exception("Почтовый ассистент: не удалось получить ответ от Ollama")
        return None

    try:
        data = json.loads(answer)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", answer, re.S)
        if not match:
            logger.warning("Почтовый ассистент: Ollama вернула не-JSON ответ: %s", answer[:300])
            return None
        try:
            data = json.loads(match.group(0))
        except (ValueError, TypeError):
            logger.warning("Почтовый ассистент: не удалось разобрать JSON от Ollama: %s", answer[:300])
            return None

    if not isinstance(data, dict):
        return None
    return data


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _parse_time(value):
    try:
        return datetime.time.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _message_key(msg):
    """Ключ письма для ProcessedEmail — message_id, а если его нет (редко,
    но бывает у Exchange), фолбэк по дате получения+теме, чтобы письмо не
    проверялось повторно каждый цикл."""
    return msg.message_id or f"no-id:{msg.datetime_received}:{msg.subject}"


def _mark_processed(message_id):
    try:
        # Своя вложенная транзакция (savepoint): если вызывается внутри
        # transaction.atomic() из _process_message, IntegrityError не должен
        # ломать всю внешнюю транзакцию.
        with transaction.atomic():
            ProcessedEmail.objects.create(message_id=message_id)
    except IntegrityError:
        # Уже помечено (гонка/повторный проход) — не страшно.
        pass


def _process_message(msg):
    message_id = _message_key(msg)
    if ProcessedEmail.objects.filter(message_id=message_id).exists():
        return False

    subject = msg.subject or ""
    body = msg.text_body or (str(msg.body) if msg.body else "") or ""

    # Письма про КПП магазина — отдельная независимая ветка: только
    # сохранение вложений, без Ollama и без Note.
    if _contains_kpp(subject, body):
        logger.info("Почтовый ассистент: письмо про КПП — %s", subject[:100])
        _save_kpp_attachments(msg)
        _mark_processed(message_id)
        return True

    # Письма от банка-эквайера о закрытии обращения в поддержку — отдельная
    # независимая ветка: без Ollama, создаёт Notification для колокольчика.
    if _is_acquirer_sender(msg) and _contains_acquirer_support_done(subject, body):
        logger.info("Почтовый ассистент: обращение по эквайрингу закрыто — %s", subject[:100])
        Notification.objects.create(text="Обращение в поддержку эквайринга выполнено", source="email")
        _mark_processed(message_id)
        return True

    # Письма от интернет-провайдера о монтаже нового канала связи — отдельная
    # независимая ветка: без Ollama, создаёт Notification для колокольчика.
    if _is_isp_sender(msg) and _contains_isp_channel_subject(subject):
        logger.info("Почтовый ассистент: смонтирован новый канал связи — %s", subject[:100])
        Notification.objects.create(text="Смонтирован новый канал связи", source="email")
        _mark_processed(message_id)
        return True

    if not _contains_trigger(subject, body):
        _mark_processed(message_id)
        return False

    logger.info("Почтовый ассистент: письмо с триггером — %s", subject[:100])
    intent = _call_llm_intent(subject, body)
    # Note и пометка "обработано" — одной транзакцией: если между ними
    # что-то упадёт, письмо просто переобработается на следующем цикле
    # (не будет ни Note, ни отметки), а не создастся вторая заметка.
    with transaction.atomic():
        if intent and intent.get("is_relevant"):
            summary = (intent.get("summary") or "").strip() or "Просьба предоставить бюджет по подразделениям"
            text = f"{summary} (письмо: «{subject}»)" if subject else summary
            note = Note.objects.create(
                text=text,
                due_date=_parse_date(intent.get("due_date")),
                due_time=_parse_time(intent.get("due_time")),
                source="email",
            )
            for attachment in _get_file_attachments(msg):
                nf = NoteFile(note=note)
                nf.file.save(
                    _safe_attachment_name(attachment.name),
                    ContentFile(attachment.content),
                    save=True,
                )
            logger.info("Почтовый ассистент: создана заметка по письму «%s»", subject[:100])

        _mark_processed(message_id)
    return True


def _connect_account():
    from exchangelib import Account, Configuration, Credentials, DELEGATE

    login = settings.EMAIL_USERNAME or settings.EMAIL_ADDRESS
    credentials = Credentials(login, settings.EMAIL_PASSWORD)
    if settings.EMAIL_SERVER:
        config = Configuration(server=settings.EMAIL_SERVER, credentials=credentials)
        return Account(
            primary_smtp_address=settings.EMAIL_ADDRESS, config=config,
            autodiscover=False, access_type=DELEGATE,
        )
    return Account(
        primary_smtp_address=settings.EMAIL_ADDRESS, credentials=credentials,
        autodiscover=True, access_type=DELEGATE,
    )


class Command(BaseCommand):
    help = "Почтовый ассистент: следит за входящей почтой и создаёт заметки о просьбах прислать бюджет"

    def handle(self, *args, **options):
        if not settings.EMAIL_ADDRESS or not settings.EMAIL_PASSWORD:
            self.stderr.write(self.style.ERROR(
                "EMAIL_ADDRESS и/или EMAIL_PASSWORD не заданы в .env — почтовый ассистент не может подключиться."
            ))
            return

        self.stdout.write("Слежу за входящими. Остановить — Ctrl+C.")

        account = None
        while True:
            # Подключение к почте — тоже внутри общего цикла: если оно упадёт
            # (при старте или после разрыва соединения), не завершаем процесс,
            # а логируем, ждём и пробуем снова — это долгоживущий процесс без
            # присмотра пользователя, как telegram_bot.py/voice_assistant.py.
            if account is None:
                try:
                    account = _connect_account()
                except KeyboardInterrupt:
                    self.stdout.write("\nОстановлено.")
                    break
                except Exception as e:
                    logger.exception("Почтовый ассистент: не удалось подключиться к почте")
                    self.stdout.write(self.style.WARNING(
                        f"Не удалось подключиться к почте ({e}), жду и пробую снова..."
                    ))
                    try:
                        time.sleep(settings.EMAIL_POLL_INTERVAL)
                    except KeyboardInterrupt:
                        self.stdout.write("\nОстановлено.")
                        break
                    continue
                self.stdout.write(self.style.SUCCESS(f"Подключено к почте {settings.EMAIL_ADDRESS}."))
                logger.info("Почтовый ассистент запущен, ящик %s", settings.EMAIL_ADDRESS)

            try:
                since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=EMAIL_LOOKBACK_DAYS)
                messages = account.inbox.filter(
                    datetime_received__gt=since
                ).order_by("-datetime_received")[:EMAIL_BATCH_LIMIT]

                new_count = 0
                created_count = 0
                for msg in messages:
                    try:
                        if ProcessedEmail.objects.filter(message_id=_message_key(msg)).exists():
                            continue
                        new_count += 1
                        had_trigger = _process_message(msg)
                        if had_trigger:
                            created_count += 1
                    except Exception:
                        logger.exception("Почтовый ассистент: ошибка обработки письма")

                if new_count:
                    logger.info(
                        "Почтовый ассистент: проверено новых писем — %s, с триггером — %s",
                        new_count, created_count,
                    )

            except KeyboardInterrupt:
                self.stdout.write("\nОстановлено.")
                break
            except Exception as e:
                logger.exception("Почтовый ассистент: ошибка при проверке почты")
                self.stdout.write(self.style.WARNING(f"Ошибка при проверке почты ({e}), жду и пробую снова..."))
                # Соединение могло разорваться — переподключимся на следующем витке.
                account = None

            try:
                time.sleep(settings.EMAIL_POLL_INTERVAL)
            except KeyboardInterrupt:
                self.stdout.write("\nОстановлено.")
                break
