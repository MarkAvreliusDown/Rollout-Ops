"""
Telegram-бот: журнал объекта, быстрые заметки и уведомления о наступившем сроке.

Как работает:
  бот сам опрашивает Telegram (long polling), внешний адрес и вебхук не нужны —
  всё крутится локально, рядом с сайтом.

Запуск (в ОТДЕЛЬНОМ окне, сайт при этом работает как обычно):
    python manage.py telegram_bot

Остановить — Ctrl+C.

Внизу экрана в Telegram всегда видны кнопки — команды искать/вспоминать не нужно:
  ✍️ Журнал         — писать в журнал объекта (если объект уже выбран —
                      мгновенно переключает режим на него же, без повторного
                      выбора филиал → раздел → объект)
  💭 Заметка        — быстрая заметка/задача без привязки к магазину
  ⚠️ Проблема       — записать проблему по выбранному объекту
  🔁 Сменить объект — выбрать другой филиал/раздел/объект
  📅 Сегодня        — что горит сегодня
  📍 Где я          — какой режим сейчас включён
  ◀ Назад           — отмена режима заметки/проблемы (вернуться в журнал),
                      либо просто открыть главное меню, если и так в журнале

Три режима записи (переключаются кнопками, объект при этом не сбрасывается —
для этого есть отдельная кнопка «🔁 Сменить объект»):
  1) Журнал объекта — всё, что пишете, падает в журнал выбранного объекта.
  2) Быстрая заметка/задача — без привязки к магазину, попадает в общий список
     заметок на главной странице сайта.
  3) Проблема — доступна только когда объект уже выбран; всё, что пишете,
     попадает в список проблем этого объекта (без вложений — модель проблем
     их не хранит).

Уведомления о сроке:
  если у задачи на сайте указано не только число, но и КОНКРЕТНОЕ ВРЕМЯ —
  бот сам напишет в чат, когда это время наступит. Работает, только пока
  бот запущен (окно с ним открыто).

Что ещё умеет:
  фото / файл, альбом (несколько вложений разом — собираются в одну запись,
  бот ждёт ~2 секунды после последнего файла)
  /objekt, /zametka, /problema, /smenit, /gde, /segodnya — то же самое, что кнопки внизу, текстом

Доступ разрешён только для chat_id из .env (TELEGRAM_CHAT_ID).
Можно указать несколько через запятую — уведомления о сроке уйдут всем сразу.
"""

import datetime
import logging
import os
import time

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from board.models import (
    BRANCH_CHOICES, Note, NoteFile, Problem, STORE_TYPE_CHOICES, Store, StoreLog, StoreLogFile, Task,
    TelegramSession,
)

logger = logging.getLogger("board")

API = "https://api.telegram.org/bot{token}/{method}"
FILE_API = "https://api.telegram.org/file/bot{token}/{path}"

BRANCH_LABELS = dict(BRANCH_CHOICES)
TYPE_LABELS = dict(STORE_TYPE_CHOICES)

PAGE_SIZE = 12  # сколько объектов показывать на одной странице

# Telegram присылает альбом (несколько фото/файлов одним сообщением от человека)
# как НЕСКОЛЬКО отдельных апдейтов с одинаковым media_group_id. Копим их здесь
# и собираем в одну запись, если новых частей не было MEDIA_GROUP_WAIT секунд.
MEDIA_GROUP_WAIT = 2.0
_pending_groups = {}

# Как часто проверять задачи с наступившим сроком (секунд).
DUE_CHECK_INTERVAL = 30.0
_last_due_check = 0.0

# Постоянные кнопки внизу экрана — заменяют команды.
BTN_JOURNAL = "✍️ Журнал"
BTN_NOTE = "💭 Заметка"
BTN_PROBLEM = "⚠️ Проблема"
BTN_CHANGE_STORE = "🔁 Сменить объект"
BTN_TODAY = "📅 Сегодня"
BTN_WHERE = "📍 Где я"
BTN_BACK = "◀ Назад"

PERSISTENT_KEYBOARD = {
    "keyboard": [
        [{"text": BTN_JOURNAL}, {"text": BTN_NOTE}],
        [{"text": BTN_PROBLEM}, {"text": BTN_CHANGE_STORE}],
        [{"text": BTN_TODAY}, {"text": BTN_WHERE}],
        [{"text": BTN_BACK}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}


# --------------------------------------------------------------------------
# Низкоуровневая работа с Telegram
# --------------------------------------------------------------------------

def api(method, **payload):
    token = settings.TELEGRAM_BOT_TOKEN
    resp = requests.post(API.format(token=token, method=method), json=payload, timeout=60)
    data = resp.json()
    if not data.get("ok"):
        logger.warning("Telegram %s вернул ошибку: %s", method, data.get("description"))
    return data


def send(chat_id, text, keyboard=None, persistent=False):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if persistent:
        payload["reply_markup"] = PERSISTENT_KEYBOARD
    elif keyboard is not None:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    return api("sendMessage", **payload)


def answer_callback(callback_id, text=None):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    return api("answerCallbackQuery", **payload)


def download_file(file_id):
    """Возвращает (имя файла, содержимое) или (None, None)."""
    token = settings.TELEGRAM_BOT_TOKEN
    info = api("getFile", file_id=file_id)
    if not info.get("ok"):
        return None, None
    path = info["result"]["file_path"]
    resp = requests.get(FILE_API.format(token=token, path=path), timeout=120)
    if resp.status_code != 200:
        return None, None
    return os.path.basename(path), resp.content


def allowed_chat_ids():
    raw = (settings.TELEGRAM_CHAT_ID or "").replace(" ", "")
    return [x for x in raw.split(",") if x]


# --------------------------------------------------------------------------
# Клавиатуры (только для вложенного выбора филиал → тип → объект)
# --------------------------------------------------------------------------

def kb_branches():
    rows = [[{"text": label, "callback_data": f"b:{code}"}] for code, label in BRANCH_CHOICES]
    return rows


def kb_types(branch):
    return [
        [{"text": label, "callback_data": f"t:{branch}:{code}:0"}]
        for code, label in STORE_TYPE_CHOICES
    ]


def kb_stores(branch, store_type, page):
    qs = Store.objects.filter(
        branch=branch, store_type=store_type, is_archived=False
    ).order_by("number")
    total = qs.count()
    start = page * PAGE_SIZE
    stores = list(qs[start:start + PAGE_SIZE])

    rows = []
    pair = []  # по два объекта в ряд — компактнее на телефоне
    for st in stores:
        pair.append({"text": st.number, "callback_data": f"s:{st.id}"})
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)

    nav = []
    if page > 0:
        nav.append({"text": "‹ Стр. назад", "callback_data": f"t:{branch}:{store_type}:{page - 1}"})
    if start + PAGE_SIZE < total:
        nav.append({"text": "Стр. вперёд ›", "callback_data": f"t:{branch}:{store_type}:{page + 1}"})
    if nav:
        rows.append(nav)

    rows.append([{"text": "‹ К типам", "callback_data": f"b:{branch}"}])
    return rows, total


# --------------------------------------------------------------------------
# Сессии
# --------------------------------------------------------------------------

def get_session(chat_id):
    session, _ = TelegramSession.objects.get_or_create(chat_id=str(chat_id))
    return session


def allowed(chat_id):
    return str(chat_id) in allowed_chat_ids()


# --------------------------------------------------------------------------
# Обработка сообщений
# --------------------------------------------------------------------------

def show_main(chat_id):
    send(
        chat_id,
        "Что делаем? Выбирайте внизу 👇\n\n"
        "✍️ Журнал — запись в журнал объекта (если объект уже выбран — просто возвращает в этот режим).\n"
        "💭 Заметка — быстрая заметка/задача без магазина.\n"
        "⚠️ Проблема — записать проблему по выбранному объекту.\n"
        "🔁 Сменить объект — выбрать другой филиал/раздел/объект.\n"
        "📅 Сегодня — что горит сегодня.\n"
        "📍 Где я — какой режим сейчас включён.\n"
        "◀ Назад — отменить заметку/проблему и вернуться в журнал (или открыть это меню).",
        persistent=True,
    )


def start_journal_flow(chat_id, session):
    """Если объект уже выбран — просто возвращает в режим журнала по нему
    (без повторного выбора филиал → раздел → объект). Иначе — как раньше,
    показывает список филиалов."""
    if session.store:
        session.mode = "log"
        session.save(update_fields=["mode"])
        send(
            chat_id,
            f"✍️ Режим журнала включён для объекта <b>{session.store.number}</b>.\n\n"
            "Пишите — всё, что пришлёте, попадёт в журнал этого объекта.",
        )
        return
    send(chat_id, "Выберите филиал:", kb_branches())


def start_change_store_flow(chat_id):
    send(chat_id, "Выберите филиал:", kb_branches())


def start_note_mode(chat_id, session):
    session.mode = "note"
    session.save(update_fields=["mode"])
    send(chat_id, "💭 Режим быстрой заметки включён.\n\nПишите что угодно — попадёт в общие заметки на главной сайта, без привязки к магазину. Так будет, пока не выберете объект через «✍️ Журнал».")


def start_problem_mode(chat_id, session):
    if not session.store:
        send(chat_id, "Сначала выберите объект — нажмите «✍️ Журнал» внизу, а потом «⚠️ Проблема».")
        return
    session.mode = "problem"
    session.save(update_fields=["mode"])
    send(
        chat_id,
        f"⚠️ Режим «Проблема» включён для объекта <b>{session.store.number}</b>.\n\n"
        "Опишите проблему одним сообщением — запишется в список проблем этого объекта. Так будет, пока не переключите режим.",
    )


def handle_back(chat_id, session):
    """Универсальная кнопка отката: из заметки/проблемы — обратно в журнал,
    из журнала — просто открывает главное меню (объект не сбрасывается)."""
    if session.mode in ("note", "problem"):
        session.mode = "log"
        session.save(update_fields=["mode"])
        if session.store:
            send(
                chat_id,
                f"✍️ Режим журнала включён для объекта <b>{session.store.number}</b>.\n\n"
                "Пишите — всё, что пришлёте, попадёт в журнал этого объекта.",
            )
        else:
            show_main(chat_id)
        return
    show_main(chat_id)


def show_today(chat_id):
    from board.views import _build_today_digest
    send(chat_id, _build_today_digest()[:4000] or "На сегодня пусто.")


def show_where(chat_id, session):
    if session.mode == "note":
        send(chat_id, "Сейчас режим: 💭 быстрая заметка (без объекта).")
    elif session.mode == "problem" and session.store:
        send(chat_id, f"Сейчас режим: ⚠️ проблема по объекту <b>{session.store.number}</b> ({session.store.get_branch_display()}).")
    elif session.store:
        send(chat_id, f"Сейчас выбран объект: <b>{session.store.number}</b> ({session.store.get_branch_display()})")
    else:
        send(chat_id, "Объект пока не выбран. Нажмите «✍️ Журнал».")


def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    data = cb.get("data", "")
    answer_callback(cb["id"])

    if not allowed(chat_id):
        send(chat_id, f"Нет доступа. Ваш chat_id: <code>{chat_id}</code>")
        return

    if data.startswith("b:"):
        branch = data.split(":", 1)[1]
        send(chat_id, f"<b>{BRANCH_LABELS.get(branch, branch)}</b> — выберите раздел:", kb_types(branch))
        return

    if data.startswith("t:"):
        _, branch, store_type, page = data.split(":")
        rows, total = kb_stores(branch, store_type, int(page))
        if total == 0:
            send(chat_id, "В этом разделе нет активных объектов.", kb_types(branch))
            return
        title = f"<b>{BRANCH_LABELS.get(branch, branch)} — {TYPE_LABELS.get(store_type, store_type)}</b>"
        send(chat_id, f"{title}\nВыберите объект (всего {total}):", rows)
        return

    if data.startswith("s:"):
        store_id = int(data.split(":", 1)[1])
        store = Store.objects.filter(id=store_id).first()
        if not store:
            send(chat_id, "Объект не найден — возможно, его удалили.")
            return
        session = get_session(chat_id)
        session.store = store
        session.mode = "log"  # выбор объекта всегда возвращает в режим журнала
        session.save(update_fields=["store", "mode"])
        send(
            chat_id,
            f"Объект: <b>{store.number}</b>\n"
            f"{store.address or 'адрес не указан'}\n\n"
            "Пишите — всё, что пришлёте дальше (текст, фото, файлы), попадёт в журнал этого объекта.",
        )
        return


def save_log_entry(store, text, files):
    """files — список кортежей (имя, содержимое)."""
    log = StoreLog.objects.create(store=store, text=text, source="tg")
    for name, content in files:
        if not content:
            continue
        lf = StoreLogFile(log=log)
        lf.file.save(name, ContentFile(content), save=True)
    return log


def save_problem(store, text):
    """Проблема по объекту — без вложений (модель Problem их не хранит)."""
    return Problem.objects.create(store=store, text=text)


def save_quick_note(text, files):
    """Общая заметка/задача без привязки к магазину — попадает на главную сайта."""
    note = Note.objects.create(text=text, source="tg")
    for name, content in files:
        if not content:
            continue
        nf = NoteFile(note=note)
        nf.file.save(name, ContentFile(content), save=True)
    return note


def _extract_files(msg):
    """Скачивает вложения из сообщения. Возвращает список (имя, содержимое)."""
    files = []
    if msg.get("photo"):
        largest = msg["photo"][-1]
        name, content = download_file(largest["file_id"])
        if content:
            files.append((name or "photo.jpg", content))
    if msg.get("document"):
        doc = msg["document"]
        name, content = download_file(doc["file_id"])
        if content:
            files.append((doc.get("file_name") or name or "file.bin", content))
    if msg.get("video"):
        name, content = download_file(msg["video"]["file_id"])
        if content:
            files.append((name or "video.mp4", content))
    return files


def _finish_entry(chat_id, mode, store, text, files):
    entry_text = text or "(без текста, только вложение)"
    suffix = f" +{len(files)} файл(ов)" if files else ""

    if mode == "note":
        save_quick_note(entry_text, files)
        send(chat_id, f"✅ Записано в общие заметки на главной{suffix}")
        logger.info("Telegram: быстрая заметка от chat %s", chat_id)
        return

    if mode == "problem":
        if not store:
            send(chat_id, "Сначала выберите объект — нажмите «✍️ Журнал» внизу, а потом «⚠️ Проблема».")
            return
        save_problem(store, entry_text)
        note = " (вложения к проблемам не сохраняются)" if files else ""
        send(chat_id, f"⚠️ Проблема записана по объекту <b>{store.number}</b>{note}")
        logger.info("Telegram: проблема по %s от chat %s", store.number, chat_id)
        return

    if not store:
        send(chat_id, "Сначала выберите объект — нажмите «✍️ Журнал» внизу.")
        return
    save_log_entry(store, entry_text, files)
    send(chat_id, f"✅ Записано в журнал <b>{store.number}</b>{suffix}")
    logger.info("Telegram: запись в журнал %s от chat %s", store.number, chat_id)


def flush_stale_groups():
    """Собирает и сохраняет альбомы, по которым давно не было новых частей."""
    now = time.time()
    stale = [gid for gid, g in _pending_groups.items() if now - g["last_update"] >= MEDIA_GROUP_WAIT]
    for gid in stale:
        group = _pending_groups.pop(gid, None)
        if not group:
            continue
        _finish_entry(group["chat_id"], group["mode"], group["store"], group["text"], group["files"])


def handle_message(msg):
    chat_id = msg["chat"]["id"]

    if not allowed(chat_id):
        send(
            chat_id,
            "Нет доступа к этому боту.\n\n"
            f"Ваш chat_id: <code>{chat_id}</code>\n"
            "Добавьте его в TELEGRAM_CHAT_ID в файле .env и перезапустите бота.",
        )
        return

    text = (msg.get("text") or msg.get("caption") or "").strip()
    session = get_session(chat_id)
    media_group_id = msg.get("media_group_id")

    # --- постоянные кнопки внизу экрана (приходят как обычный текст) ---
    if text == BTN_JOURNAL and not media_group_id:
        start_journal_flow(chat_id, session)
        return
    if text == BTN_NOTE and not media_group_id:
        start_note_mode(chat_id, session)
        return
    if text == BTN_PROBLEM and not media_group_id:
        start_problem_mode(chat_id, session)
        return
    if text == BTN_CHANGE_STORE and not media_group_id:
        start_change_store_flow(chat_id)
        return
    if text == BTN_TODAY and not media_group_id:
        show_today(chat_id)
        return
    if text == BTN_WHERE and not media_group_id:
        show_where(chat_id, session)
        return
    if text == BTN_BACK and not media_group_id:
        handle_back(chat_id, session)
        return

    # --- команды текстом (у альбомов текст — подпись, командой быть не может) ---
    if text.startswith("/") and not media_group_id:
        cmd = text.split()[0].lstrip("/").split("@")[0].lower()
        if cmd in ("start", "menu"):
            show_main(chat_id)
            return
        if cmd in ("objekt", "object", "obj"):
            start_journal_flow(chat_id, session)
            return
        if cmd in ("zametka", "note"):
            start_note_mode(chat_id, session)
            return
        if cmd in ("problema", "problem"):
            start_problem_mode(chat_id, session)
            return
        if cmd in ("smenit", "change"):
            start_change_store_flow(chat_id)
            return
        if cmd in ("gde", "where"):
            show_where(chat_id, session)
            return
        if cmd in ("segodnya", "today"):
            show_today(chat_id)
            return
        send(chat_id, "Не знаю такую команду. Кнопки внизу подскажут, что можно.", persistent=True)
        return

    files = _extract_files(msg)

    # --- альбом: копим части, сохраняем одной записью чуть позже ---
    if media_group_id:
        group = _pending_groups.setdefault(media_group_id, {
            "chat_id": chat_id,
            "mode": session.mode,
            "store": session.store,
            "text": "",
            "files": [],
            "last_update": time.time(),
        })
        if text and not group["text"]:
            group["text"] = text  # подпись обычно есть только у одной части альбома
        group["files"].extend(files)
        group["last_update"] = time.time()
        return

    if not text and not files:
        send(chat_id, "Пустое сообщение. Напишите текст или пришлите фото.")
        return

    _finish_entry(chat_id, session.mode, session.store, text, files)


# --------------------------------------------------------------------------
# Уведомления о наступившем сроке задачи
# --------------------------------------------------------------------------

def check_due_tasks():
    """Ищет задачи с указанным конкретным временем, срок которых уже наступил,
    и шлёт уведомление всем разрешённым chat_id. Каждой задаче — одно уведомление."""
    chat_ids = allowed_chat_ids()
    if not chat_ids:
        return

    now = timezone.localtime()
    due_tasks = Task.objects.filter(
        due_date=now.date(), due_time__isnull=False, notified_at__isnull=True,
        store__is_archived=False,
    ).exclude(status="done").select_related("store")

    for task in due_tasks:
        due_dt = timezone.make_aware(datetime.datetime.combine(now.date(), task.due_time))
        if due_dt > now:
            continue  # время ещё не подошло
        text = (
            f"⏰ Время подошло: <b>{task.title}</b>\n"
            f"{task.store.get_branch_display()} · {task.store.number} · {task.due_time.strftime('%H:%M')}"
        )
        for chat_id in chat_ids:
            send(chat_id, text)
        task.notified_at = now
        task.save(update_fields=["notified_at"])
        logger.info("Telegram: уведомление о сроке — задача %s (%s)", task.title, task.store.number)


def check_due_notes():
    """Аналог check_due_tasks() для заметок с указанным временем."""
    chat_ids = allowed_chat_ids()
    if not chat_ids:
        return

    now = timezone.localtime()
    due_notes = Note.objects.filter(
        due_date=now.date(), due_time__isnull=False, notified_at__isnull=True, is_archived=False,
    ).select_related("task__store")

    for note in due_notes:
        due_dt = timezone.make_aware(datetime.datetime.combine(now.date(), note.due_time))
        if due_dt > now:
            continue  # время ещё не подошло
        store_line = ""
        if note.task_id:
            store_line = f"{note.task.store.get_branch_display()} · {note.task.store.number} · "
        text = f"⏰ Время подошло: <b>{note.text}</b>\n{store_line}{note.due_time.strftime('%H:%M')}"
        for chat_id in chat_ids:
            send(chat_id, text)
        note.notified_at = now
        note.save(update_fields=["notified_at"])
        logger.info("Telegram: уведомление о сроке — заметка %s", note.id)


# --------------------------------------------------------------------------
# Основной цикл
# --------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Telegram-бот: журнал, быстрые заметки и уведомления о сроке (long polling)"

    def handle(self, *args, **options):
        global _last_due_check

        if not settings.TELEGRAM_BOT_TOKEN:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN не задан в .env"))
            return
        if not settings.TELEGRAM_CHAT_ID:
            self.stdout.write(self.style.WARNING(
                "TELEGRAM_CHAT_ID не задан — бот никого не пустит. "
                "Напишите боту любое сообщение, он подскажет ваш chat_id."
            ))

        me = api("getMe")
        if me.get("ok"):
            self.stdout.write(self.style.SUCCESS(f"Бот @{me['result'].get('username')} запущен."))
        else:
            self.stdout.write(self.style.ERROR("Не удалось подключиться — проверьте токен."))
            return
        self.stdout.write("Слушаю сообщения. Остановить — Ctrl+C.")

        offset = None
        while True:
            try:
                # если есть недособранный альбом — опрашиваем чаще, чтобы вовремя его собрать
                poll_timeout = 2 if _pending_groups else 30
                resp = requests.get(
                    API.format(token=settings.TELEGRAM_BOT_TOKEN, method="getUpdates"),
                    params={"timeout": poll_timeout, "offset": offset},
                    timeout=poll_timeout + 30,
                )
                data = resp.json()
                if not data.get("ok"):
                    self.stdout.write(self.style.WARNING(f"Telegram: {data.get('description')}"))
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        if "callback_query" in update:
                            handle_callback(update["callback_query"])
                        elif "message" in update:
                            handle_message(update["message"])
                    except Exception as e:
                        logger.exception("Ошибка обработки сообщения Telegram: %s", e)
                        self.stdout.write(self.style.ERROR(f"Ошибка: {e}"))

                flush_stale_groups()

                if time.time() - _last_due_check >= DUE_CHECK_INTERVAL:
                    _last_due_check = time.time()
                    check_due_tasks()
                    check_due_notes()

            except KeyboardInterrupt:
                self.stdout.write("\nОстановлено.")
                break
            except requests.RequestException as e:
                self.stdout.write(self.style.WARNING(f"Сеть недоступна ({e}), жду 10 секунд..."))
                time.sleep(10)
            except Exception as e:
                logger.exception("Непредвиденная ошибка бота: %s", e)
                self.stdout.write(self.style.ERROR(f"Непредвиденная ошибка: {e}"))
                time.sleep(5)
