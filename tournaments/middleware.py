from django.conf import settings


class SetLanguageCookieMiddleware:
    """
    After login, if the signal attached `_set_language_cookie` to the request,
    set the Django language cookie on the response so the choice persists.
    """
    COOKIE_NAME = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')
    COOKIE_AGE = getattr(settings, 'LANGUAGE_COOKIE_AGE', None)
    COOKIE_PATH = getattr(settings, 'LANGUAGE_COOKIE_PATH', '/')
    COOKIE_DOMAIN = getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None)
    COOKIE_SECURE = getattr(settings, 'LANGUAGE_COOKIE_SECURE', False)
    COOKIE_HTTPONLY = getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False)
    COOKIE_SAMESITE = getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', 'Lax')

    def __init__(self, get_response):
        """Store the next middleware/callable in the chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Set the language cookie when a language switch was requested."""
        response = self.get_response(request)
        lang = getattr(request, '_set_language_cookie', None)
        if lang:
            response.set_cookie(
                self.COOKIE_NAME,
                lang,
                max_age=self.COOKIE_AGE,
                path=self.COOKIE_PATH,
                domain=self.COOKIE_DOMAIN,
                secure=self.COOKIE_SECURE,
                httponly=self.COOKIE_HTTPONLY,
                samesite=self.COOKIE_SAMESITE,
            )
        return response
