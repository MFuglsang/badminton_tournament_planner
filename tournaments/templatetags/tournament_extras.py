from django import template

register = template.Library()


@register.filter
def split(value, sep):
    """Split a string by *sep* and return a list."""
    if value:
        return value.split(sep)
    return [value]


@register.filter
def dict_get(d, key):
    """Look up *key* in dict *d*. Returns '' if not found."""
    if isinstance(d, dict):
        return d.get(key, '')
    return ''


@register.filter
def unix_ts(dt):
    """Convert a datetime to a Unix timestamp integer for JS timers."""
    if dt is None:
        return ''
    try:
        return int(dt.timestamp())
    except Exception:
        return ''
