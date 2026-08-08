from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from board.icons import COLOR_CHOICES, ICON_CHOICES, resolve_task_icon, task_icon

register = template.Library()


@register.filter
def get_item(d, key):
    """
    Достаёт значение по ключу из dict в шаблоне. Нужен для канбана на главной:
    columns — dict {status: [Store, ...]}, а порядок и подписи колонок идут из
    kanban_statuses (список пар status/label) — точечная запись Django-шаблонов
    (`columns.status`) не умеет резолвить key как переменную, только как
    буквальную строку, поэтому без этого фильтра подписи пришлось бы хардкодить.
    """
    if d is None:
        return None
    return d.get(key)


@register.simple_tag
def task_icon_badge(task_or_title):
    """
    Кружок с иконкой Tabler. Если передана задача (объект Task) — учитывается
    её ручной выбор иконки, если он есть. Если передана просто строка —
    иконка подбирается только по словам в названии (старый способ вызова).
    """
    if hasattr(task_or_title, "title"):
        icon, color = resolve_task_icon(task_or_title)
    else:
        icon, color = task_icon(task_or_title)
    return format_html(
        '<span class="icon-badge icon-badge-{}"><i class="ti ti-{}" aria-hidden="true"></i></span>',
        color, icon,
    )


@register.simple_tag
def icon_picker(selected_icon="", selected_color=""):
    """
    Ряд кружков-иконок для ручного выбора (радио-кнопки icon_name) + отдельный
    ряд кружков-цветов (радио-кнопки icon_color). Пустое значение icon_name = «Авто»,
    иконка тогда подбирается по названию задачи автоматически.
    """
    parts = ['<div class="icon-picker">']

    auto_checked = mark_safe("checked") if not selected_icon else ""
    parts.append(format_html(
        '<label class="icon-picker-opt icon-picker-auto" title="Авто (по названию)">'
        '<input type="radio" name="icon_name" value="" {}><span>авто</span></label>',
        auto_checked,
    ))
    for icon_name, label in ICON_CHOICES:
        checked = mark_safe("checked") if icon_name == selected_icon else ""
        parts.append(format_html(
            '<label class="icon-picker-opt icon-badge icon-badge-accent" title="{}">'
            '<input type="radio" name="icon_name" value="{}" {}>'
            '<i class="ti ti-{}" aria-hidden="true"></i></label>',
            label, icon_name, checked, icon_name,
        ))
    parts.append('</div>')

    parts.append('<div class="icon-picker-colors">')
    for color_code, label in COLOR_CHOICES:
        checked = mark_safe("checked") if (
            color_code == selected_color or (not selected_color and color_code == "accent")
        ) else ""
        parts.append(format_html(
            '<label class="icon-picker-color icon-badge icon-badge-{}" title="{}">'
            '<input type="radio" name="icon_color" value="{}" {}></label>',
            color_code, label, color_code, checked,
        ))
    parts.append('</div>')

    return mark_safe("".join(parts))
