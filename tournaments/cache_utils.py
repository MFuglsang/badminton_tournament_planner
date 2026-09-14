"""Tiny view-cache decorator for the anonymous public views.

Behaves like django.views.decorators.cache.cache_page, but also stamps an
X-Cache: HIT/MISS response header so nginx access logs can report cache hit
ratios for Phase 5 (production monitoring) without adding new infrastructure.
"""
import functools

from django.core.cache import cache
from django.http import HttpResponse


def cache_page_with_status(timeout, key_prefix='pubcache'):
    """Cache a view's 200 responses in the default cache for `timeout` seconds."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            cache_key = f'{key_prefix}:{request.get_full_path()}'
            cached = cache.get(cache_key)
            if cached is not None:
                response = HttpResponse(
                    cached['content'], content_type=cached['content_type'], status=cached['status']
                )
                response['X-Cache'] = 'HIT'
                return response
            response = view_func(request, *args, **kwargs)
            if response.status_code == 200:
                cache.set(cache_key, {
                    'content': response.content,
                    'content_type': response.get('Content-Type', 'text/html'),
                    'status': response.status_code,
                }, timeout)
            response['X-Cache'] = 'MISS'
            return response
        return wrapper
    return decorator
