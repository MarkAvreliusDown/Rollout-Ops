
import datetime
import ipaddress

from django.db import models
from django.utils import timezone


BRANCH_CHOICES = [
    ("szf", "Филиал 1"),
    ("uf", "Филиал 2"),
    ("pf", "Филиал 3"),
    ("cf", "Филиал 4"),
]

STORE_TYPE_CHOICES = [
    ("opening", "Новые Магазины"),
    ("reconstruction", "Реконструкция"),
    ("extra", "Доп. работы"),
    ("closing", "Закрытие"),
]

RECONSTRUCTION_KIND_CHOICES = [
    ("full", "Полная"),
    ("partial", "Частичная"),
    ("mini", "Мини"),
]

EXTRA_KIND_CHOICES = [
    ("extra_kso", "Установка доп. КСО"),
]

# Стадия готовности магазина на канбане на главной странице — выставляется/двигается
# пользователем вручную (drag-and-drop), не связана со статусом задач (TASK_STATUS_CHOICES)
# и не связана с типом магазина (STORE_TYPE_CHOICES).
STORE_KANBAN_STATUS_CHOICES = [
    ("new", "Новый"),
    ("progress", "В работе"),
    ("review", "Проверка"),
    ("open", "Открыт"),
]

TASK_STATUS_CHOICES = [
    ("progress", "В работе"),
    ("waiting", "Ждём подрядчика"),
    ("done", "Готово"),
]

ANCHOR_CHOICES = [
    ("opening", "Открытие"),
    ("vpk2", "ВПК-2"),
]

AREA_FORMAT_CHOICES = [
    ("200", "200"),
    ("300", "300"),
    ("400", "400"),
    ("500/600", "500/600"),
]

CONTRACTOR_CHOICES = [
    ("Союз-76", "Союз-76"),
    ("Принтград", "Принтград"),
    ("НВ", "НВ"),
    ("Дата Крат", "Дата Крат"),
    ("Бизнес Содействие", "Бизнес Содействие"),
]

# Точки доступа по умолчанию для формата (можно поправить вручную при создании магазина).
ACCESS_POINTS_DEFAULT_BY_FORMAT = {
    "200": "3",
    "300": "3",
    "400": "5",
    "500/600": "",
}


class Store(models.Model):
    branch = models.CharField("Филиал", max_length=10, choices=BRANCH_CHOICES)
    store_type = models.CharField("Тип", max_length=20, choices=STORE_TYPE_CHOICES)
    number = models.CharField("№ объекта", max_length=50)
    address = models.CharField("Адрес", max_length=300, blank=True)
    region = models.CharField("Регион", max_length=100, blank=True)
    contact = models.CharField("Подрядчик", max_length=200, blank=True, choices=CONTRACTOR_CHOICES)
    notes = models.TextField("Заметки", blank=True)
    is_archived = models.BooleanField("В архиве", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    # Подрядчики, выбранные при создании магазина (названия вкладок-компаний в письмах) —
    # используются, чтобы при создании магазина и при появлении дат задач автоматически
    # заполнялась строка в соответствующих таблицах на странице "Письма".
    contractors = models.JSONField("Подрядчики (для писем)", default=list, blank=True)
    kso_count = models.CharField("Кол-во КСО", max_length=50, blank=True, default="")
    cash_count = models.CharField("Кол-во касс", max_length=50, blank=True, default="")
    area_format = models.CharField("Формат по площади", max_length=20, choices=AREA_FORMAT_CHOICES, blank=True, default="")
    columns_count = models.CharField("Кол-во колонок", max_length=50, blank=True, default="")
    columns_type = models.CharField("Тип колонок", max_length=100, blank=True, default="")
    has_meat_scale = models.BooleanField("Весы «мясо» на объекте", default=False)
    access_points_count = models.CharField("Кол-во точек доступа", max_length=50, blank=True, default="")

    # Поля для выгрузки строки в рабочий Excel-файл пользователя (кнопка "Скопировать
    # строку для Excel" на карточке магазина) — см. _build_store_excel_row в views.py.
    license_number = models.CharField("Лицензия для касс", max_length=255, blank=True, default="")
    kpp = models.CharField("КПП", max_length=255, blank=True, default="")
    cluster = models.CharField("Кластер", max_length=255, blank=True, default="")
    ibp_count = models.CharField("Кол-во ИБП", max_length=255, blank=True, default="")
    provider = models.CharField("Провайдер", max_length=255, blank=True, default="")

    # Поля для генератора строк таблицы АСЦН (см. StoreCashRegister/_build_ascn_rows в views.py).
    locality = models.CharField("Населённый пункт", max_length=200, blank=True, default="")
    fsrar_id = models.CharField("FSRAR_ID", max_length=50, blank=True, default="")

    # Стадия готовности на канбане главной страницы (см. STORE_KANBAN_STATUS_CHOICES).
    kanban_status = models.CharField(
        "Стадия", max_length=20, choices=STORE_KANBAN_STATUS_CHOICES, default="new"
    )

    reconstruction_kind = models.CharField(
        "Вид реконструкции", max_length=20, choices=RECONSTRUCTION_KIND_CHOICES,
        blank=True, default="",
    )

    extra_kind = models.CharField(
        "Вид работ", max_length=20, choices=EXTRA_KIND_CHOICES, blank=True, default=""
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"

    def __str__(self):
        return f"{self.number} ({self.get_branch_display()})"

    @property
    def open_tasks_count(self):
        return self.tasks.exclude(status="done").count()

    @property
    def checklist_total(self):
        return self.checklist_items.count()

    @property
    def checklist_done(self):
        return self.checklist_items.filter(is_checked=True).count()

    @property
    def progress_percent(self):
        tasks = list(self.tasks.all())
        if not tasks:
            return 0
        done = sum(1 for t in tasks if t.status == "done")
        return round(done * 100 / len(tasks))


class Task(models.Model):
    store = models.ForeignKey(Store, related_name="tasks", on_delete=models.CASCADE)
    parent = models.ForeignKey(
        "self", related_name="subtasks", on_delete=models.CASCADE, null=True, blank=True,
        verbose_name="Родительская задача",
    )
    title = models.CharField("Задача", max_length=300)
    due_date = models.DateField("Срок", null=True, blank=True)
    due_time = models.TimeField("Время", null=True, blank=True)  # необязательно — можно оставить только дату
    status = models.CharField("Статус", max_length=20, choices=TASK_STATUS_CHOICES, default="progress")
    order = models.IntegerField("Порядок", default=0)

    # Если это опорная задача (Открытие / ВПК-2) — anchor_key задаёт, какой она является опорой.
    anchor_key = models.CharField("Ключ опорной даты", max_length=10, choices=ANCHOR_CHOICES, null=True, blank=True)
    # Если дата этой задачи считается от опорной — от какой именно и с каким смещением в днях.
    depends_on = models.CharField("Зависит от", max_length=10, choices=ANCHOR_CHOICES, null=True, blank=True)
    offset_days = models.IntegerField("Смещение (дней)", null=True, blank=True)

    # Иконка выбрана вручную (необязательно) — если пусто, подбирается автоматически по названию.
    icon_name = models.CharField("Иконка", max_length=30, blank=True)
    icon_color = models.CharField("Цвет иконки", max_length=10, blank=True)

    # Когда бот отправил уведомление "время подошло" — чтобы не слать его повторно.
    # Сбрасывается в None при любом изменении срока/времени задачи.
    notified_at = models.DateTimeField("Уведомление отправлено", null=True, blank=True)

    # Момент перехода статуса в "done" — для карточек вроде "выполнено сегодня".
    # Проставляется/сбрасывается автоматически в save() при смене статуса.
    completed_at = models.DateTimeField("Выполнено", null=True, blank=True)

    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # due_date иногда приходит строкой "YYYY-MM-DD" (из HTML-формы) — Django сам
        # разберёт её при записи в БД, но self.due_date в Python до перезагрузки останется
        # строкой, а strftime() ниже ждёт объект date.
        if isinstance(self.due_date, str):
            self.due_date = datetime.date.fromisoformat(self.due_date) if self.due_date else None
        is_new = self.pk is None
        had_no_date = is_new or Task.objects.filter(pk=self.pk, due_date__isnull=True).exists()
        old_status = None if is_new else Task.objects.filter(pk=self.pk).values_list("status", flat=True).first()
        if self.status == "done" and old_status != "done":
            self.completed_at = timezone.now()
        elif old_status == "done" and self.status != "done":
            self.completed_at = None
        super().save(*args, **kwargs)
        if self.due_date is not None and had_no_date:
            _sync_task_date_to_letters(self)


class Report(models.Model):
    store = models.ForeignKey(Store, related_name="reports", on_delete=models.CASCADE)
    draft_text = models.TextField("Черновик", blank=True)
    final_text = models.TextField("Итоговый отчёт", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Отчёт"
        verbose_name_plural = "Отчёты"

    def __str__(self):
        return f"Отчёт по {self.store.number} от {self.created_at:%d.%m.%Y}"


class ReportPhoto(models.Model):
    report = models.ForeignKey(Report, related_name="photos", on_delete=models.CASCADE)
    file = models.FileField("Файл", upload_to="reports/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Файл отчёта"
        verbose_name_plural = "Файлы отчётов"

    @property
    def is_image(self):
        return self.file.name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

    @property
    def filename(self):
        return self.file.name.split("/")[-1]


class Note(models.Model):
    text = models.TextField("Текст заметки")
    due_date = models.DateField("Дата", null=True, blank=True)
    due_time = models.TimeField("Время", null=True, blank=True)  # необязательно — можно оставить только дату
    task = models.ForeignKey(
        "Task", related_name="notes", on_delete=models.CASCADE, null=True, blank=True
    )
    is_archived = models.BooleanField("В архиве", default=False)
    source = models.CharField("Источник", max_length=10, default="web")
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    notified_at = models.DateTimeField("Уведомление отправлено", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заметка"
        verbose_name_plural = "Заметки"

    def __str__(self):
        return self.text[:50]


class NoteFile(models.Model):
    note = models.ForeignKey(Note, related_name="files", on_delete=models.CASCADE)
    file = models.FileField("Файл", upload_to="notes/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Файл заметки"
        verbose_name_plural = "Файлы заметок"

    def __str__(self):
        return self.file.name.split("/")[-1]


class Contact(models.Model):
    store = models.ForeignKey(Store, related_name="contacts", on_delete=models.CASCADE, null=True, blank=True)
    branch = models.CharField("Филиал", max_length=10, choices=BRANCH_CHOICES, blank=True)
    name = models.CharField("Имя", max_length=150)
    role = models.CharField("Роль / компания", max_length=150, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    telegram = models.CharField("Telegram (username)", max_length=100, blank=True)
    max_contact = models.CharField("MAX (username)", max_length=100, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Контакт"
        verbose_name_plural = "Контакты"

    def __str__(self):
        return self.name

    @property
    def effective_branch(self):
        if self.store_id:
            return self.store.branch
        return self.branch

    @property
    def telegram_url(self):
        if not self.telegram:
            return ""
        handle = self.telegram.strip().lstrip("@")
        if handle.startswith("http"):
            return handle
        return f"https://t.me/{handle}"

    @property
    def max_url(self):
        if not self.max_contact:
            return ""
        handle = self.max_contact.strip()
        if handle.startswith("http"):
            return handle
        return f"https://max.ru/{handle}"


class Problem(models.Model):
    """Журнал проблем по магазину — работает одинаково для всех типов (открытие,
    реконструкция, доп. работы, закрытие). Несколько записей по времени, каждую
    можно отметить решённой/нерешённой — в отличие от Store.notes (одно поле)."""

    store = models.ForeignKey(Store, related_name="problems", on_delete=models.CASCADE, verbose_name="Магазин")
    text = models.TextField("Проблема")
    is_resolved = models.BooleanField("Решено", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    resolved_at = models.DateTimeField("Решено когда", null=True, blank=True)

    class Meta:
        ordering = ["is_resolved", "-created_at"]
        verbose_name = "Проблема"
        verbose_name_plural = "Проблемы"

    def __str__(self):
        return f"{self.store.number}: {self.text[:40]}"


class KbCategory(models.Model):
    name = models.CharField("Название", max_length=200)
    image = models.ImageField("Картинка", upload_to="kb_categories/%Y/%m/%d/")
    image_has_caption = models.BooleanField("Подпись уже в картинке", default=False)
    order = models.PositiveIntegerField("Порядок", default=0)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категория базы знаний"
        verbose_name_plural = "Категории базы знаний"

    def __str__(self):
        return self.name


class Article(models.Model):
    title = models.CharField("Заголовок", max_length=300)
    content = models.TextField("Содержимое", blank=True)
    category = models.ForeignKey(KbCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="articles", verbose_name="Категория")
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Статья базы знаний"
        verbose_name_plural = "База знаний"

    def __str__(self):
        return self.title


class ArticleImage(models.Model):
    article = models.ForeignKey(Article, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField("Картинка", upload_to="kb_images/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Картинка статьи"
        verbose_name_plural = "Картинки статей"


class ArticleFile(models.Model):
    article = models.ForeignKey(Article, related_name="files", on_delete=models.CASCADE)
    file = models.FileField("Файл", upload_to="kb_files/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Файл статьи"
        verbose_name_plural = "Файлы статей"

    @property
    def filename(self):
        return self.file.name.split("/")[-1]


class KbCategoryFile(models.Model):
    # null = файл лежит в разделе "Без категории"; при удалении категории
    # файлы не удаляются, а "переезжают" в Без категории (SET_NULL)
    category = models.ForeignKey(KbCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="files")
    file = models.FileField("Файл", upload_to="kb_category_files/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Файл категории базы знаний"
        verbose_name_plural = "Файлы категорий базы знаний"

    @property
    def filename(self):
        return self.file.name.split("/")[-1]


class ChecklistItem(models.Model):
    store = models.ForeignKey(Store, related_name="checklist_items", on_delete=models.CASCADE)
    text = models.CharField("Пункт", max_length=300)
    category = models.CharField("Раздел", max_length=100, blank=True, default="")
    is_checked = models.BooleanField("Отмечено", default=False)
    order = models.IntegerField("Порядок", default=0)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Пункт чек-листа"
        verbose_name_plural = "Чек-лист"

    def __str__(self):
        return self.text


class StoreCashRegister(models.Model):
    """Строка кассы (КСО) магазина для генератора строк таблицы АСЦН."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="cash_registers")
    order = models.PositiveIntegerField("Порядок", default=0)
    number = models.CharField("Номер КСО", max_length=20, blank=True, default="")
    loymax_data = models.TextField("LOYMAX posid/login/password", blank=True, default="")
    sbp_terminal = models.CharField("Номер терминала СБП", max_length=50, blank=True, default="")
    sbp_link = models.CharField("Кассовая ссылка СБП", max_length=255, blank=True, default="")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"КСО {self.number or self.order} — {self.store}"


class SalarySettings(models.Model):
    base_oklad = models.IntegerField("Оклад до вычета НДФЛ", default=90000)
    ndfl_percent = models.DecimalField("НДФЛ, %", max_digits=4, decimal_places=1, default=13)

    class Meta:
        verbose_name = "Настройки зарплаты"
        verbose_name_plural = "Настройки зарплаты"

    def __str__(self):
        return f"Оклад {self.base_oklad} ₽, НДФЛ {self.ndfl_percent}%"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Bonus(models.Model):
    year = models.IntegerField("Год")
    month = models.IntegerField("Месяц")  # 1-12
    amount = models.IntegerField("Сумма премии до вычета НДФЛ")
    description = models.CharField("За что", max_length=300, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["-year", "-month", "-created_at"]
        verbose_name = "Премия"
        verbose_name_plural = "Премии"

    def __str__(self):
        return f"{self.month:02d}.{self.year} — {self.amount} ₽ ({self.description})"


class ReconstructionRecord(models.Model):
    branch = models.CharField("Филиал", max_length=10, choices=BRANCH_CHOICES, blank=True)
    store_number = models.CharField("№ объекта", max_length=50)
    reconstruction_date = models.DateField("Дата реконструкции", null=True, blank=True)
    expected_amount = models.IntegerField("Ожидаемая премия", null=True, blank=True)
    paid = models.BooleanField("Выплачено", default=False)
    paid_date = models.DateField("Дата выплаты", null=True, blank=True)
    notes = models.TextField("Заметки", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["paid", "-reconstruction_date"]
        verbose_name = "Реконструкция (премии)"
        verbose_name_plural = "Реконструкции (премии)"

    def __str__(self):
        return f"{self.store_number} — {self.reconstruction_date}"


class ReconstructionDocument(models.Model):
    record = models.ForeignKey(ReconstructionRecord, related_name="documents", on_delete=models.CASCADE)
    file = models.FileField("Файл", upload_to="reconstruction_docs/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Документ реконструкции"
        verbose_name_plural = "Документы реконструкций"

    @property
    def filename(self):
        return self.file.name.split("/")[-1]


LOG_SOURCE_CHOICES = [
    ("web", "Сайт"),
    ("tg", "Telegram"),
    ("report", "Из старого отчёта"),
    ("voice", "Голосовой ассистент"),
]


class StoreLog(models.Model):
    """Журнал по объекту — короткие записи по ходу работ."""

    store = models.ForeignKey(Store, related_name="logs", on_delete=models.CASCADE, verbose_name="Магазин")
    text = models.TextField("Запись")
    created_at = models.DateTimeField("Когда", default=timezone.now)
    source = models.CharField("Источник", max_length=10, choices=LOG_SOURCE_CHOICES, default="web")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал"

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} — {self.text[:40]}"


class StoreLogFile(models.Model):
    log = models.ForeignKey(StoreLog, related_name="files", on_delete=models.CASCADE)
    file = models.FileField("Файл", upload_to="logs_files/%Y/%m/%d/")
    uploaded_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Файл журнала"
        verbose_name_plural = "Файлы журнала"

    def __str__(self):
        return self.file.name.split("/")[-1]

    @property
    def is_image(self):
        return self.file.name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

    @property
    def filename(self):
        return self.file.name.split("/")[-1]


class TelegramSession(models.Model):
    """Кто из Telegram какой объект сейчас выбрал (чтобы бот помнил между сообщениями)."""

    chat_id = models.CharField("Chat ID", max_length=50, unique=True)
    store = models.ForeignKey(
        Store, related_name="tg_sessions", on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Выбранный объект",
    )
    # "log" — обычная запись в журнал выбранного объекта (по умолчанию);
    # "note" — режим быстрой заметки/задачи без привязки к магазину.
    mode = models.CharField("Режим", max_length=20, default="log")
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Сессия Telegram"
        verbose_name_plural = "Сессии Telegram"

    def __str__(self):
        return f"{self.chat_id} → {self.store or 'объект не выбран'}"


class LetterCompany(models.Model):
    """Вкладка-компания в генераторе писем (таблица графика работ + получатели)."""

    PAGE_CHOICES = [
        ("schedules", "Графики работ"),
        ("accounts", "Создание учёток"),
    ]

    key = models.CharField("Ключ", max_length=64, unique=True)
    page = models.CharField("Страница", max_length=20, choices=PAGE_CHOICES, default="schedules")
    name = models.CharField("Название", max_length=200)
    order = models.PositiveIntegerField("Порядок", default=0)
    header = models.CharField("Шапка письма", max_length=200, blank=True, default="")
    subject = models.CharField("Тема письма", max_length=300, blank=True, default="")
    recipients = models.TextField("Получатели", blank=True, default="")
    columns = models.JSONField("Столбцы", default=list)
    rows = models.JSONField("Строки", default=list)
    # Показывать эту компанию в списке подрядчиков при создании магазина
    # и подставлять в неё данные автоматически (см. Store.contractors).
    is_store_contractor = models.BooleanField("Подрядчик при создании магазина", default=False)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Компания (письма)"
        verbose_name_plural = "Компании (письма)"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


def _store_autofill_values(store, router_values=None):
    """Значения магазина для столбцов письма, помеченных соответствующим тегом (кроме дат задач)."""
    columns_count_and_type = " ".join(x for x in [store.columns_count, store.columns_type] if x)
    values = {
        "branch": store.get_branch_display(),
        "number": store.number,
        "address": store.address,
        "region": store.region,
        "kso_count": store.kso_count,
        "cash_count": store.cash_count,
        "area_format": store.area_format,
        "columns_count": store.columns_count,
        "columns_type": store.columns_type,
        "columns_count_and_type": columns_count_and_type,
        "has_meat_scale": "Да" if store.has_meat_scale else "Нет",
        "access_points_count": store.access_points_count,
    }
    if router_values and router_values.get("WANIP2") and router_values.get("WANGW2"):
        values["wan_ip2_reserve"] = f"{router_values['WANIP2']}/30, шлюз {router_values['WANGW2']}"
    return values


def sync_new_store_to_letters(store, router_values=None):
    """При создании магазина добавляет по строке в таблицы писем выбранных подрядчиков
    (Store.contractors — названия должны совпадать с названиями вкладок-компаний).
    Столбцы с тегом "task_date:..." при этом остаются пустыми — даты задач ещё не заданы,
    их дозаполнит _sync_task_date_to_letters, когда дата впервые появится."""
    if not store.contractors:
        return
    values = _store_autofill_values(store, router_values)
    companies = LetterCompany.objects.filter(name__in=store.contractors, is_store_contractor=True)
    for company in companies:
        row = [values.get(col.get("autofill") or "", "") for col in company.columns]
        company.rows.append(row)
        company.save(update_fields=["rows", "updated_at"])


def _sync_task_date_to_letters(task):
    """Когда у задачи впервые появляется дата (была пустой) — дозаполняет соответствующую
    пустую ячейку в письмах у строки этого магазина. Дальнейшие переносы даты уже не трогают
    письмо — там правят вручную."""
    store = task.store
    if not store.contractors:
        return
    branch_label = store.get_branch_display()
    tag = f"task_date:{task.title}"
    date_str = task.due_date.strftime("%d.%m.%Y")
    companies = LetterCompany.objects.filter(name__in=store.contractors, is_store_contractor=True)
    for company in companies:
        branch_idx = number_idx = date_idx = None
        for i, col in enumerate(company.columns):
            af = col.get("autofill")
            if af == "branch":
                branch_idx = i
            elif af == "number":
                number_idx = i
            elif af == tag:
                date_idx = i
        if date_idx is None or branch_idx is None or number_idx is None:
            continue
        changed = False
        for row in company.rows:
            if len(row) <= max(branch_idx, number_idx, date_idx):
                continue
            if row[branch_idx] == branch_label and row[number_idx] == store.number and not row[date_idx]:
                row[date_idx] = date_str
                changed = True
        if changed:
            company.save(update_fields=["rows", "updated_at"])


class Contractor(models.Model):
    """Подрядчик для расчёта бюджета — хранит прайс-лист по умолчанию
    (оборудование и виды работ), который копируется в BudgetCalculation
    при создании расчёта и подставляется заново при смене подрядчика."""

    # Стабильный ключ, генерируется на клиенте при создании новой карточки подрядчика в
    # редакторе прайс-листов — позволяет сохранять весь список одним autosave-запросом
    # (update_or_create по key), не путаясь с ещё не полученным id новой записи. См. паттерн
    # LetterCompany.key.
    key = models.CharField("Ключ", max_length=64, unique=True)
    name = models.CharField("Название", max_length=200, unique=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    # [{"title": str, "qty": number, "unit_price": number}, ...]
    equipment_rows = models.JSONField("Оборудование (прайс)", default=list, blank=True)
    # [{"title": str, "qty": number, "unit_price": number,
    #   "section": "main"|"kso", "is_scs": bool}, ...]
    work_rows = models.JSONField("Виды работ (прайс)", default=list, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Подрядчик (бюджет)"
        verbose_name_plural = "Подрядчики (бюджет)"

    def __str__(self):
        return self.name


class BudgetSettings(models.Model):
    """Общие настройки расчёта бюджета (сейчас — ставка НДС)."""

    vat_rate = models.DecimalField("Ставка НДС, %", max_digits=4, decimal_places=1, default=22)

    class Meta:
        verbose_name = "Настройки бюджета"
        verbose_name_plural = "Настройки бюджета"

    def __str__(self):
        return f"НДС {self.vat_rate}%"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BudgetCalculation(models.Model):
    """Расчёт бюджета по конкретному объекту у выбранного подрядчика.
    Оборудование/работы — рабочая копия прайса подрядчика на момент создания,
    правки не влияют на сам прайс-лист подрядчика."""

    contractor = models.ForeignKey(
        Contractor, null=True, blank=True, on_delete=models.SET_NULL, related_name="calculations"
    )
    contractor_name = models.CharField("Подрядчик (снимок)", max_length=200, blank=True)
    title = models.CharField("Название/номер объекта", max_length=200)
    branch = models.CharField("Филиал", max_length=10, choices=BRANCH_CHOICES, blank=True)
    store_number = models.CharField("№ объекта", max_length=50, blank=True)
    is_archived = models.BooleanField("В архиве", default=False)
    vat_rate = models.DecimalField("Ставка НДС, %", max_digits=4, decimal_places=1, default=22)
    premium = models.DecimalField("Премия", max_digits=10, decimal_places=2, default=4000)
    equipment_rows = models.JSONField(default=list, blank=True)
    work_rows = models.JSONField(default=list, blank=True)
    # [{"label": str, "qty": number}, ...] — блок "Расчёт ТД" (кол-во точек по зонам,
    # сумма которых даёт кол-во портов СКС для строки с is_scs=True в work_rows)
    td_zones = models.JSONField(default=list, blank=True)
    total_amount = models.DecimalField("Итого", max_digits=12, decimal_places=2, default=0)
    reconstruction = models.ForeignKey(
        ReconstructionRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="budget_calcs"
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Расчёт бюджета"
        verbose_name_plural = "Расчёты бюджетов"

    def __str__(self):
        return f"{self.title} — {self.contractor_name}"


def compute_budget_totals(equipment_rows, work_rows, td_zones, vat_rate, premium):
    """Считает суммы по категориям для расчёта бюджета (плашки
    оборудование/пнр ксо/пнр/скс/премия/общее и итог). НДС применяется
    единообразно (vat_rate, %) ко всем строкам блока "виды работ";
    оборудование — без НДС, как в исходном файле."""
    vat_mult = 1 + (float(vat_rate or 0) / 100)
    scs_qty = sum(float(z.get("qty") or 0) for z in (td_zones or []))

    equipment_total = sum(float(r.get("unit_price") or 0) * float(r.get("qty") or 0) for r in (equipment_rows or []))

    work_total = 0.0
    kso_total = 0.0
    scs_total = 0.0
    for row in work_rows or []:
        price = float(row.get("unit_price") or 0)
        if row.get("is_scs"):
            qty = scs_qty if td_zones else float(row.get("qty") or 0)
            scs_total += price * qty * vat_mult
        elif row.get("section") == "kso":
            kso_total += price * float(row.get("qty") or 0) * vat_mult
        else:
            work_total += price * float(row.get("qty") or 0) * vat_mult

    premium = float(premium or 0)
    grand_total = equipment_total + kso_total + work_total + scs_total + premium
    return {
        "equipment_total": round(equipment_total, 2),
        "kso_total": round(kso_total, 2),
        "work_total": round(work_total, 2),
        "scs_total": round(scs_total, 2),
        "scs_qty": scs_qty,
        "premium": round(premium, 2),
        "grand_total": round(grand_total, 2),
    }


class RouterConfigTemplate(models.Model):
    """Singleton: текст шаблона конфига роутера с плейсхолдерами вида <NAME>,
    редактируется на сайте (страница /router-config/template/)."""

    template_text = models.TextField("Текст шаблона", blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Шаблон конфига роутера"
        verbose_name_plural = "Шаблон конфига роутера"

    def __str__(self):
        return "Шаблон конфига роутера"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class StoreRouterConfig(models.Model):
    """Сохранённые значения плейсхолдеров конфига роутера для магазина."""

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="router_config")
    values = models.JSONField("Значения полей", default=dict, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    def __str__(self):
        return f"Конфиг роутера — {self.store}"


class StoreDeviceIPConfig(models.Model):
    """Сохранённые IP-адреса конечных устройств магазина (4-й сегмент сети),
    считаются от NETWORK конфига роутера. Отдельно от StoreRouterConfig,
    чтобы сохранение конфига роутера их не затирало."""

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name="device_ip_config")
    values = models.JSONField("Значения адресов устройств", default=dict, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    def __str__(self):
        return f"IP устройств — {self.store}"


ROUTER_IP_ANCHORS = {
    "szf": {
        "base_number": 1000,
        "provider2_ip": "10.0.1.10",
        "tunnel_ip": "10.0.2.10",
        "network": "10.0.3.0",
    },
    "uf": {
        "base_number": 2000,
        "provider2_ip": "10.0.1.50",
        "tunnel_ip": "10.0.2.50",
        "network": "10.0.4.0",
    },
    "pf": {
        "base_number": 3000,
        "provider2_ip": "10.0.1.90",
        "tunnel_ip": "10.0.2.90",
        "network": "10.0.5.0",
    },
    # cf (Филиал 4) намеренно отсутствует — данных по нему нет, автозаполнение не работает
}


def compute_router_config_for_store(store):
    """Вычисляет автозначения полей конфига роутера (провайдер 2/LAN, без
    провайдера 1) для нового магазина по номеру, если для филиала есть якорь
    в ROUTER_IP_ANCHORS.
    Возвращает dict или None, если якоря нет или номер магазина не целое число."""
    anchor = ROUTER_IP_ANCHORS.get(store.branch)
    if not anchor:
        return None
    try:
        offset = int(store.number) - anchor["base_number"]

        provider2_ip = ipaddress.IPv4Address(anchor["provider2_ip"]) + 4 * offset
        provider2_gw = provider2_ip - 1
        tunnel_ip = ipaddress.IPv4Address(anchor["tunnel_ip"]) + offset

        base_net = ipaddress.IPv4Address(anchor["network"])
        o1, o2, base_third, base_half = base_net.packed
        hn_anchor = base_third * 2 + (1 if base_half == 128 else 0)
        hn = hn_anchor + offset
        new_third = hn // 2
        new_half = 128 if hn % 2 == 1 else 0
        network = ipaddress.IPv4Address(bytes([o1, o2, new_third % 256, new_half]))
        network_gw = network + 1
    except (TypeError, ValueError):
        # Странный/нечисловой номер магазина или офсет за пределами диапазона
        # IPv4 (например, опечатка в номере) — просто не считаем автозначения,
        # не роняем создание магазина.
        return None

    network_base = str(network)
    if new_half == 0:
        dhcp_start = f"{network_base.rsplit('.', 1)[0]}.64"
        dhcp_end = f"{network_base.rsplit('.', 1)[0]}.95"
    else:
        dhcp_start = f"{network_base.rsplit('.', 1)[0]}.192"
        dhcp_end = f"{network_base.rsplit('.', 1)[0]}.233"

    return {
        "SHOPID": store.number,
        "WANIP2": str(provider2_ip),
        "WANMASK2": "255.255.255.252",
        "WANGW2": str(provider2_gw),
        "TUNIP2": str(tunnel_ip),
        "NETWORK": network_base,
        "LANIP": str(network_gw),
        "LANMASK": "255.255.255.128",
        "DHCPSTART": dhcp_start,
        "DHCPEND": dhcp_end,
    }


DEVICE_IP_OFFSETS = {
    "DEV_GATEWAY": 1,
    "DEV_PC1": 4,
    "DEV_PC2": 5,
    "DEV_VIDEOREG": 12,
    "DEV_SERVER_KSO": 48,
    "DEV_ADM": 52,
}
DEVICE_DNS1 = "192.168.241.2"
DEVICE_DNS2 = "192.168.241.3"
DEVICE_MASK = "255.255.255.128"
DEVICE_IP_LABELS = {
    "DEV_GATEWAY": "Шлюз",
    "DEV_PC1": "Комп 1 (СТС)",
    "DEV_PC2": "Комп 2 (ДМ)",
    "DEV_VIDEOREG": "Видеорегистратор",
    "DEV_SERVER_KSO": "Сервер КСО",
    "DEV_ADM": "АДМ",
    "DEV_MASK": "Маска",
    "DEV_DNS1": "DNS 1",
    "DEV_DNS2": "DNS 2",
}


def compute_device_ips_for_network(network_str):
    """Вычисляет IP-адреса конечных устройств (шлюз/компы/видеорегистратор/
    сервер КСО/АДМ) как фиксированное смещение от начала подсети NETWORK.
    Возвращает dict или None, если network_str пуст/не парсится."""
    if not network_str:
        return None
    try:
        base = ipaddress.IPv4Address(network_str)
        result = {key: str(base + offset) for key, offset in DEVICE_IP_OFFSETS.items()}
    except (TypeError, ValueError):
        # Пустая/некорректная подсеть или офсет за пределами диапазона IPv4.
        return None

    result["DEV_MASK"] = DEVICE_MASK
    result["DEV_DNS1"] = DEVICE_DNS1
    result["DEV_DNS2"] = DEVICE_DNS2
    return result


COMPANY_INN = "7729705354"
KSO_NUMBER_BASE = 11
KSO_IP_SB_OFFSET_BASE = 24
KSO_IP_FR_OFFSET_BASE = 40


def compute_kso_ips(network_str, order):
    """IP СБ/ФР/шлюза для кассы с индексом order (0-based) в подсети network_str.
    Возвращает dict {"ip_sb", "ip_fr", "gw"} или None, если сеть не задана/не парсится."""
    if not network_str:
        return None
    try:
        base = ipaddress.IPv4Address(network_str)
        return {
            "ip_sb": str(base + KSO_IP_SB_OFFSET_BASE + order),
            "ip_fr": str(base + KSO_IP_FR_OFFSET_BASE + order),
            "gw": str(base + DEVICE_IP_OFFSETS["DEV_GATEWAY"]),
        }
    except (TypeError, ValueError):
        return None


class Notification(models.Model):
    """Уведомление для колокольчика на сайте (сейчас создаётся только
    почтовым ассистентом, но source оставлен свободным полем на будущее)."""

    text = models.CharField("Текст", max_length=300)
    source = models.CharField("Источник", max_length=20, default="email")
    is_read = models.BooleanField("Прочитано", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return self.text[:50]


class ProcessedEmail(models.Model):
    """Служебная запись для дедупликации — какие письма уже разобраны почтовым
    ассистентом (email_watcher), чтобы не создавать заметку по одному письму дважды."""

    message_id = models.CharField("ID письма", max_length=255, unique=True)
    processed_at = models.DateTimeField("Обработано", auto_now_add=True)

    class Meta:
        verbose_name = "Обработанное письмо"
        verbose_name_plural = "Обработанные письма"

    def __str__(self):
        return self.message_id
