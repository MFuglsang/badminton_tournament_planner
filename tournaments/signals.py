from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import translation
from django.conf import settings as django_settings

LANGUAGE_COOKIE_NAME = getattr(django_settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
LANGUAGE_COOKIE_AGE = getattr(django_settings, 'LANGUAGE_COOKIE_AGE', None)
LANGUAGE_COOKIE_DOMAIN = getattr(django_settings, 'LANGUAGE_COOKIE_DOMAIN', None)
LANGUAGE_COOKIE_PATH = getattr(django_settings, 'LANGUAGE_COOKIE_PATH', '/')
LANGUAGE_COOKIE_SECURE = getattr(django_settings, 'LANGUAGE_COOKIE_SECURE', False)
LANGUAGE_COOKIE_HTTPONLY = getattr(django_settings, 'LANGUAGE_COOKIE_HTTPONLY', False)
LANGUAGE_COOKIE_SAMESITE = getattr(django_settings, 'LANGUAGE_COOKIE_SAMESITE', 'Lax')


@receiver(user_logged_in)
def set_language_on_login(sender, request, user, **kwargs):
    """Activate the club's preferred language after login and persist it via cookie."""
    # Only apply if the user hasn't already chosen a language via the switcher
    if LANGUAGE_COOKIE_NAME in request.COOKIES:
        return
    try:
        lang = user.profile.language
    except Exception:
        return
    if lang:
        translation.activate(lang)
        # Store on response — Django's LocaleMiddleware will pick this up,
        # but we also need to set it on the response object.
        # We attach it to the request so the login view's response can set it.
        request._set_language_cookie = lang
