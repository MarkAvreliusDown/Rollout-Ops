"""
Простая защита паролем на весь сайт — без логинов и пользователей, один
общий пароль на всех. Подходит для локального инструмента одного человека.

Как работает: если пароль не введён в этом браузере (нет отметки в сессии),
любая страница перенаправляет на /login/. Пароль хранится в .env
(SITE_PASSWORD), в коде его нет. Если SITE_PASSWORD пустой — защита
отключается, сайт открыт как раньше (например, для отладки).
"""

from django.conf import settings
from django.shortcuts import redirect

# Эти пути должны быть доступны ДО входа — иначе страницу логина будет не
# на чем показать (нужны статика и сама страница логина).
EXEMPT_PREFIXES = ("/login/", "/static/", "/media/")

SESSION_KEY = "site_authenticated"


class SitePasswordMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.SITE_PASSWORD:
            return self.get_response(request)

        if request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        if request.session.get(SESSION_KEY):
            return self.get_response(request)

        return redirect(f"/login/?next={request.path}")


class NoBrowserCacheMiddleware:
    """
    Стили и скрипты лежат прямо в HTML-шаблонах (без отдельных .css/.js), и
    браузер иногда кеширует саму страницу целиком — после правки шаблона
    пользователь видит старую версию, пока вручную не почистит кэш. Заголовок
    ниже запрещает браузеру использовать сохранённую копию страницы без
    проверки у сервера, чтобы правки сразу были видны на обычном обновлении
    (F5). На папку /media/ (фото/файлы отчётов) не действует — там кеш не
    мешает.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/media/"):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
