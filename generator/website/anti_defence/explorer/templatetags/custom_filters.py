from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from explorer.utils.data_utils import load_eco_map, ECO_RE

register = template.Library()

@register.filter
def split(value, delimiter):
    return value.split(",")[0].split(delimiter)[0] if delimiter in value else value

@register.filter
def split_all(value, delimiter):
    return value.split(delimiter)

@register.filter
def first_part_lower(value, delimiter="_"):
    """Splits the string by delimiter and returns the first part in lowercase."""
    return value.split(delimiter)[0].lower() if delimiter in value else value.lower()

@register.filter
def force_string(value):
    """Ensures the value is always treated as a string."""
    return str(value)

ECO_MAP = load_eco_map()

@register.filter(is_safe=True)
def eco_tooltip(value):
    """
    Replaces ECO tokens with <span class="eco" data-short="..." data-full="...">ECO_...</span>.
    The input is escaped first (safe for untrusted content).
    """
    if not value:
        return ''

    escaped = escape(value)

    def repl(m):
        code = m.group(1)
        info = ECO_MAP.get(code)
        if info:
            # Escape both short and full definitions
            short_esc = escape(info.get('short', ''))
            full_esc = escape(info.get('definition', ''))
            return (f'<span class="eco" '
                    f'data-short="{short_esc}" '
                    f'data-full="{full_esc}" '
                    f'title="{short_esc}">{code}</span>')
        return code

    html = ECO_RE.sub(repl, escaped)
    return mark_safe(html)