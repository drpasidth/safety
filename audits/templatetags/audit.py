from django import template

from core import thaidate

register = template.Library()

STATUS_COLOR = {"C": "success", "IP": "warning", "NS": "danger", "": "secondary"}
STATUS_ICON = {"C": "check-circle-fill", "IP": "hourglass-split", "NS": "x-circle-fill", "": "dash-circle"}


@register.filter
def thai_long(value):
    return thaidate.long(value)


@register.filter
def thai_short(value):
    return thaidate.short(value)


@register.filter
def getitem(mapping, key):
    return mapping.get(key, "") if mapping else ""


@register.filter
def status_color(status):
    return STATUS_COLOR.get(status or "", "secondary")


@register.filter
def status_icon(status):
    return STATUS_ICON.get(status or "", "dash-circle")


@register.filter
def level_label(level):
    if level is None:
        return "—"
    return f"SC{level}" if level else "ยังไม่ถึง SC1"


@register.filter
def lines(text):
    return [ln.strip().lstrip("-•").strip() for ln in (text or "").splitlines() if ln.strip()]
