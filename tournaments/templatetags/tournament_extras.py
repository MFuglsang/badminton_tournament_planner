from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Look up *key* in dict *d*. Returns '' if not found."""
    if isinstance(d, dict):
        return d.get(key, '')
    return ''
