import re
from decimal import Decimal

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def som(value):
    """12500 -> "12 500" (thousands separated by a space, as written in Uzbekistan)."""
    if value in (None, ""):
        return ""
    return f"{int(value):,}".replace(",", " ")


@register.filter
def qty(value):
    """Decimal("10.000") -> "10", Decimal("0.500") -> "0.5".

    Decimal.normalize() is avoided on purpose: it turns 10 into "1E+1".
    """
    if value in (None, ""):
        return ""
    text = format(Decimal(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


@register.filter
def local_name(obj):
    """``name_ru`` when the active language is Russian and it is filled in, else ``name``."""
    return obj.local_name


@register.filter
def percent_change(new, old):
    if not old:
        return 0
    return round((new - old) * 100 / old)


@register.filter
def highlight_hashtags(telegram_html):
    """Colour hashtags in the preview. Input is already escaped Telegram HTML (posts.formatting)."""
    return mark_safe(re.sub(r"(?<![\w&])#\w+", r'<span class="tg-hashtag">\g<0></span>', telegram_html))
