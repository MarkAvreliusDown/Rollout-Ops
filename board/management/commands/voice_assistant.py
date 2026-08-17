"""
Голосовой ассистент "Пал Лаич" — постоянно слушает микрофон, реагирует на
кодовое слово "Пал Лаич" и по голосовой команде создаёт запись в базе
(общая заметка / запись в журнал магазина / проблема по магазину).

Запуск (в ОТДЕЛЬНОМ окне, сайт и telegram-бот при этом работают как обычно):
    python manage.py voice_assistant

Остановить — Ctrl+C.

Как работает:
  1) Микрофон слушается постоянно (sounddevice), простым energy-based VAD
     (по громкости блоков звука) определяется, где говорят, а где тишина.
  2) Как только фраза закончилась — короткое окно речи проверяется маленькой
     моделью распознавания (faster-whisper "tiny") на совпадение со словом
     "Пал Лаич" (нечёткое сравнение, т.к. tiny-модель может ошибаться на
     1-2 буквы в коротком слове).
  3) Если слово похоже на "Пал Лаич" — ассистент отвечает "Слушаю" и
     записывает следующую фразу (саму команду) до паузы.
  4) Команда распознаётся уже большой моделью ("medium", как у голосовых
     сообщений в Telegram-боте) и отправляется в локальную Ollama-модель
     для разбора: что за действие (заметка / журнал / проблема) и по какому
     магазину.
  5) Создаётся соответствующая запись в базе, ассистент озвучивает
     подтверждение (Silero TTS, офлайн синтез речи).

Всё работает полностью локально, без интернета — так же, как faster-whisper
для голосовых сообщений в Telegram и Ollama для ИИ-чата на сайте.

Известные ограничения v1:
  - Возможны ложные срабатывания/пропуски слова «Пал Лаич» — маленькая
    tiny-модель на коротком слове не идеальна.
  - Работает только пока запущен вручную отдельным окном, нужен постоянный
    доступ к микрофону.
  - Если номер магазина есть в нескольких филиалах — берётся первый
    найденный, с голосовым объявлением филиала.
  - Ошибка в распознавании номера -> запись уходит в обычные заметки с
    пометкой, а не привязывается «на угад».
  - Один говорящий, тихое помещение.
  - Первый запуск подгружает обе whisper-модели (tiny + medium) — пауза и
    место на диске.
  - Первый запуск после этого обновления скачивает модель Silero TTS через
    интернет (несколько десятков МБ, один раз, дальше кэшируется на диске
    и работает офлайн) — аналогично тому, как уже скачиваются модели
    faster-whisper.

Специальные команды без ИИ:
  - Фраза «Пал Лаич, начинаем движуху» распознаётся сразу по тексту команды
    (нечёткое сравнение, как у будильного слова), минуя разбор через Ollama
    (_call_llm_intent). Запускает файл с музыкой в проигрывателе по
    умолчанию Windows (os.startfile) и озвучивает подтверждение. Путь к
    файлу настраивается через .env (VOICE_MUSIC_FILE), по умолчанию
    "C:\\projects\\rabota\\музыка для движухи\\Движуха бесконечна.mp3".
  - Фраза «Пал Лаич, как дела» или «Пал Лаич, ты тут» — проверка связи:
    ассистент просто отвечает голосом "На связи, всё слышу и работаю
    нормально", тоже минуя Ollama. Ничего не создаёт и не пишет в базу.
"""

import difflib
import json
import logging
import os
import queue
import re
import time
import winsound

import numpy as np
import sounddevice as sd
from django.core.management.base import BaseCommand

from board.models import Note, Problem, Store, StoreLog
from board.views import _call_llm

logger = logging.getLogger("board")

SAMPLE_RATE = 16000
BLOCK_MS = 30  # длина одного блока звука для VAD, мс
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_MS / 1000)

# Порог энергии (RMS по int16-блоку), выше которого блок считается речью.
# Можно подстроить под конкретный микрофон/помещение через .env/переменную окружения.
ENERGY_THRESHOLD = int(os.environ.get("VOICE_ENERGY_THRESHOLD", "300"))

# Голос Silero TTS (v4_ru), можно переопределить через переменную окружения.
VOICE_TTS_SPEAKER = os.environ.get("VOICE_TTS_SPEAKER", "aidar")

# Файл с музыкой для спецкоманды "начинаем движуху", можно переопределить через .env.
MUSIC_FILE_PATH = os.environ.get(
    "VOICE_MUSIC_FILE",
    r"C:\projects\rabota\музыка для движухи\Движуха бесконечна.mp3",
)

WAKE_MAX_SECONDS = 4.0          # макс. окно накопления речи для проверки будильного слова
WAKE_SILENCE_MS = 700           # тишина, которой заканчивается фраза-кандидат на "Пал Лаич"
COMMAND_SILENCE_MS = 1400       # тишина, которой заканчивается сама команда
COMMAND_MAX_SECONDS = 15.0      # макс. длина записи команды

# Минимум именно ГРОМКИХ блоков подряд/суммарно, чтобы вообще считать это
# кандидатом на слово, а не случайным шумом (шум компа, музыка на фоне,
# короткий щелчок) — отсекает ложные срабатывания ДО бипа и распознавания.
MIN_WAKE_LOUD_MS = 250
MIN_WAKE_LOUD_BLOCKS = max(1, int(MIN_WAKE_LOUD_MS / BLOCK_MS))

WAKE_WORDS = [
    "пал лаич", "пал лайч", "пол лаич", "пал ляич", "пал лэйч",
    "паллаич", "поллаич",
]
WAKE_MATCH_RATIO = 0.6

VALID_ACTIONS = ("note", "log", "problem")


# --------------------------------------------------------------------------
# Ленивая загрузка моделей распознавания речи
# --------------------------------------------------------------------------

_wake_model = None
_command_model = None
_tts_model = None


def _get_wake_model():
    global _wake_model
    if _wake_model is None:
        from faster_whisper import WhisperModel
        logger.info("Голосовой ассистент: загружаю модель для будильного слова (faster-whisper tiny)...")
        _wake_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("Голосовой ассистент: модель для будильного слова загружена.")
    return _wake_model


def _get_command_model():
    global _command_model
    if _command_model is None:
        from faster_whisper import WhisperModel
        logger.info("Голосовой ассистент: загружаю модель для команд (faster-whisper medium)...")
        _command_model = WhisperModel("medium", device="cpu", compute_type="int8")
        logger.info("Голосовой ассистент: модель для команд загружена.")
    return _command_model


def _get_tts_model():
    global _tts_model
    if _tts_model is None:
        import torch
        logger.info("Голосовой ассистент: загружаю модель озвучки (Silero TTS)...")
        _tts_model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language="ru",
            speaker="v4_ru",
        )
        logger.info("Голосовой ассистент: модель озвучки загружена.")
    return _tts_model


def _transcribe(model, audio_np):
    """audio_np — float32 numpy-массив в диапазоне [-1, 1], 16кГц, моно."""
    try:
        segments, _info = model.transcribe(audio_np, language="ru", vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()
    except Exception:
        logger.exception("Голосовой ассистент: ошибка распознавания речи")
        return ""


# --------------------------------------------------------------------------
# Будильное слово
# --------------------------------------------------------------------------

def _normalize(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_wake_word(text):
    norm = _normalize(text)
    if not norm:
        return False
    words = norm.split()
    if not words:
        return False

    candidates = list(words)
    # whisper иногда разбивает короткое слово на два — сравниваем и биграммы
    for i in range(len(words) - 1):
        candidates.append(words[i] + words[i + 1])

    for candidate in candidates:
        for wake in WAKE_WORDS:
            ratio = difflib.SequenceMatcher(None, candidate, wake).ratio()
            if ratio >= WAKE_MATCH_RATIO:
                return True
    return False


# --------------------------------------------------------------------------
# Спецкоманда "начинаем движуху" — без разбора через Ollama
# --------------------------------------------------------------------------

MUSIC_START_WORDS = ("начинаем", "начать", "запускаем", "включаем")
MUSIC_TRIGGER_WORDS = ("движуха", "движуху", "движухи")
MUSIC_MATCH_RATIO = 0.7


def _looks_like_music_command(text):
    norm = _normalize(text)
    if not norm:
        return False
    words = norm.split()
    has_start = any(
        difflib.SequenceMatcher(None, w, sw).ratio() >= MUSIC_MATCH_RATIO
        for w in words for sw in MUSIC_START_WORDS
    )
    has_movement = any(
        difflib.SequenceMatcher(None, w, mw).ratio() >= MUSIC_MATCH_RATIO
        for w in words for mw in MUSIC_TRIGGER_WORDS
    )
    return has_start and has_movement


def _play_music():
    try:
        if not os.path.exists(MUSIC_FILE_PATH):
            logger.warning("Голосовой ассистент: файл музыки не найден: %s", MUSIC_FILE_PATH)
            _speak("Файл с музыкой не найден")
            return
        os.startfile(MUSIC_FILE_PATH)
        logger.info("Голосовой ассистент: запускаю музыку: %s", MUSIC_FILE_PATH)
        _speak("Начинаем движуху")
    except Exception:
        logger.exception("Голосовой ассистент: не удалось запустить музыку")
        _speak("Не получилось запустить музыку")


# --------------------------------------------------------------------------
# Спецкоманда "как дела" / "ты тут" — проверка связи, без ИИ и без базы
# --------------------------------------------------------------------------

STATUS_TRIGGER_PHRASES = ("как дела", "ты тут")
STATUS_MATCH_RATIO = 0.75


def _looks_like_status_command(text):
    norm = _normalize(text)
    if not norm:
        return False
    return any(
        difflib.SequenceMatcher(None, norm, phrase).ratio() >= STATUS_MATCH_RATIO
        for phrase in STATUS_TRIGGER_PHRASES
    )


def _reply_status():
    logger.info("Голосовой ассистент: проверка связи")
    _speak("На связи, всё слышу и работаю нормально")


# --------------------------------------------------------------------------
# Речь -> действие через Ollama
# --------------------------------------------------------------------------

INTENT_PROMPT = """Ты — модуль разбора голосовых команд для системы учёта магазинов.
Тебе дан текст команды, надиктованной голосом (могут быть ошибки распознавания речи).
Определи:
- action: одно из "note" (просто заметка/задача, без магазина), "log" (запись в журнал магазина), "problem" (проблема по магазину)
- store_number: номер магазина, если он назван (просто число или короткий код как в речи, например "магазин 45" -> "45"), иначе null
- text: сама суть записи (без слов вроде "запиши в журнал магазина 45 что...", только содержательная часть)

Верни СТРОГО один JSON-объект без пояснений, без markdown, без ```. Формат:
{{"action": "note|log|problem", "store_number": "45" или null, "text": "..."}}

Команда: "{command}"
"""


def _call_llm_intent(text):
    """Возвращает dict {action, store_number, text} или None, если разобрать не удалось."""
    prompt = INTENT_PROMPT.format(command=text)
    try:
        resp = _call_llm(prompt, timeout=60)
        data_raw = resp.json()
        candidates = data_raw.get("candidates") or []
        if not candidates:
            logger.warning("Голосовой ассистент: Ollama вернула ошибку вместо ответа: %s", data_raw)
            return None
        answer = candidates[0]["content"]["parts"][0]["text"].strip()
    except Exception:
        logger.exception("Голосовой ассистент: не удалось получить ответ от Ollama")
        return None

    try:
        data = json.loads(answer)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", answer, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except (ValueError, TypeError):
            return None

    if not isinstance(data, dict) or data.get("action") not in VALID_ACTIONS:
        return None
    return data


# --------------------------------------------------------------------------
# Резолвинг магазина по номеру
# --------------------------------------------------------------------------

def _resolve_store(store_number):
    """Возвращает (store, spoken_note) — store может быть None, если не нашли."""
    stores = list(Store.objects.filter(number=store_number, is_archived=False).order_by("id"))
    if not stores:
        return None, None
    if len(stores) == 1:
        return stores[0], None
    store = stores[0]
    note = f"Магазинов с номером {store_number} несколько, взял первый — {store.get_branch_display()}."
    return store, note


# --------------------------------------------------------------------------
# Выполнение команды
# --------------------------------------------------------------------------

def _handle_command(text):
    if _looks_like_music_command(text):
        _play_music()
        return

    if _looks_like_status_command(text):
        _reply_status()
        return

    intent = _call_llm_intent(text)
    if not intent:
        Note.objects.create(text=f"[голос, не разобрано]: {text}", source="voice")
        logger.info("Голосовой ассистент: не разобрал команду, сохранил как заметку: %s", text)
        _speak("Не разобрал команду, записал как заметку")
        return

    action = intent.get("action")
    store_number = (intent.get("store_number") or "").strip() or None
    body = (intent.get("text") or "").strip() or text

    if action == "note":
        Note.objects.create(text=body, source="voice")
        logger.info("Голосовой ассистент: заметка сохранена: %s", body)
        _speak("Заметка сохранена")
        return

    if not store_number:
        Note.objects.create(text=f"[голос, номер магазина не назван] {body}", source="voice")
        logger.info("Голосовой ассистент: номер магазина не назван, сохранил как заметку: %s", body)
        _speak("Не расслышал номер магазина, записал как обычную заметку")
        return

    store, spoken_note = _resolve_store(store_number)
    if not store:
        Note.objects.create(text=f"[голос, магазин {store_number} не найден] {body}", source="voice")
        logger.info("Голосовой ассистент: магазин %s не найден, сохранил как заметку", store_number)
        _speak(f"Магазин номер {store_number} не найден, сохранил как обычную заметку")
        return

    if action == "log":
        StoreLog.objects.create(store=store, text=body, source="voice")
        logger.info("Голосовой ассистент: запись в журнал %s: %s", store.number, body)
        if spoken_note:
            _speak(f"Записал в журнал магазина {store.number}. {spoken_note}")
        else:
            _speak(f"Записал в журнал магазина {store.number}")
        return

    if action == "problem":
        Problem.objects.create(store=store, text=body)
        logger.info("Голосовой ассистент: проблема по %s: %s", store.number, body)
        if spoken_note:
            _speak(f"Записал проблему по магазину {store.number}. {spoken_note}")
        else:
            _speak(f"Записал проблему по магазину {store.number}")
        return


def _speak(text):
    try:
        audio = _get_tts_model().apply_tts(text=text, speaker=VOICE_TTS_SPEAKER, sample_rate=48000)
        sd.play(audio.numpy() if hasattr(audio, "numpy") else audio, 48000)
        sd.wait()
    except Exception:
        logger.exception("Голосовой ассистент: ошибка озвучки")


# --------------------------------------------------------------------------
# Захват звука и VAD
# --------------------------------------------------------------------------

def _block_rms(block):
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block.astype(np.float64)))))


def _int16_to_float32(block):
    return (block.astype(np.float32)) / 32768.0


class Command(BaseCommand):
    help = 'Голосовой ассистент "Пал Лаич" — постоянное прослушивание микрофона (см. докстринг файла)'

    def handle(self, *args, **options):
        q = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning("Голосовой ассистент: статус звукового потока: %s", status)
            q.put(indata.copy().reshape(-1))

        self.stdout.write(self.style.SUCCESS('Голосовой ассистент "Пал Лаич" запущен. Говорите "Пал Лаич" и команду.'))
        self.stdout.write("Остановить — Ctrl+C.")
        logger.info("Голосовой ассистент запущен.")

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                blocksize=BLOCK_SIZE, callback=audio_callback,
            ):
                self._listen_loop(q)
        except KeyboardInterrupt:
            self.stdout.write("\nОстановлено.")
        except Exception as e:
            logger.exception("Голосовой ассистент: непредвиденная ошибка")
            self.stdout.write(self.style.ERROR(f"Непредвиденная ошибка: {e}"))

    def _listen_loop(self, q):
        silence_blocks_wake = max(1, int(WAKE_SILENCE_MS / BLOCK_MS))
        silence_blocks_command = max(1, int(COMMAND_SILENCE_MS / BLOCK_MS))
        max_blocks_wake = int(WAKE_MAX_SECONDS * 1000 / BLOCK_MS)
        max_blocks_command = int(COMMAND_MAX_SECONDS * 1000 / BLOCK_MS)

        while True:
            # --- ждём начала речи ---
            buffer_blocks = []
            speaking = False
            silence_run = 0
            loud_count = 0

            while True:
                try:
                    block = q.get(timeout=1.0)
                except queue.Empty:
                    continue

                is_loud = _block_rms(block) >= ENERGY_THRESHOLD

                if not speaking:
                    if is_loud:
                        speaking = True
                        buffer_blocks = [block]
                        silence_run = 0
                        loud_count = 1
                    continue

                buffer_blocks.append(block)
                if is_loud:
                    silence_run = 0
                    loud_count += 1
                else:
                    silence_run += 1

                if silence_run >= silence_blocks_wake or len(buffer_blocks) >= max_blocks_wake:
                    break

            audio = np.concatenate(buffer_blocks) if buffer_blocks else np.array([], dtype=np.int16)
            if audio.size == 0:
                continue

            # Случайный короткий шум (щелчок, гул) отсекаем ДО бипа и распознавания —
            # не набралось достаточно именно громких блоков подряд/суммарно.
            if loud_count < MIN_WAKE_LOUD_BLOCKS:
                continue

            # Короткий сигнал сразу, как только уловили речь достаточной громкости —
            # не зависит от распознавания, даёт мгновенное подтверждение "микрофон слышит".
            try:
                winsound.Beep(880, 100)
            except Exception:
                logger.warning("Голосовой ассистент: не удалось воспроизвести сигнал (winsound.Beep)")

            wake_text = _transcribe(_get_wake_model(), _int16_to_float32(audio))
            self.stdout.write(f'Расслышал: "{wake_text}"' if wake_text else "Расслышал: (пусто)")
            if not wake_text or not _looks_like_wake_word(wake_text):
                continue

            logger.info('Голосовой ассистент: услышал будильное слово ("%s")', wake_text)
            _drain_queue(q)
            _speak("Слушаю")
            _drain_queue(q)  # не слушаем собственный голос как начало команды

            # --- запись самой команды ---
            cmd_blocks = []
            speaking = False
            silence_run = 0
            started_at = time.time()

            while True:
                try:
                    block = q.get(timeout=1.0)
                except queue.Empty:
                    if time.time() - started_at >= COMMAND_MAX_SECONDS:
                        break
                    continue

                is_loud = _block_rms(block) >= ENERGY_THRESHOLD

                if not speaking:
                    if is_loud:
                        speaking = True
                        cmd_blocks = [block]
                        silence_run = 0
                    elif time.time() - started_at >= COMMAND_MAX_SECONDS:
                        break
                    continue

                cmd_blocks.append(block)
                if is_loud:
                    silence_run = 0
                else:
                    silence_run += 1

                if silence_run >= silence_blocks_command or len(cmd_blocks) >= max_blocks_command:
                    break

            if not cmd_blocks:
                continue

            cmd_audio = np.concatenate(cmd_blocks)
            command_text = _transcribe(_get_command_model(), _int16_to_float32(cmd_audio))
            if not command_text:
                continue

            self.stdout.write(f"Команда: {command_text}")
            logger.info("Голосовой ассистент: команда распознана: %s", command_text)
            _handle_command(command_text)
            _drain_queue(q)


def _drain_queue(q):
    """Сбрасывает накопившийся в очереди звук (например, пока играло TTS)."""
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass
