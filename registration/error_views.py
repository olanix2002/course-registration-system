"""The CSRF failure page.

Django calls the view named by settings.CSRF_FAILURE_VIEW when a request
arrives without a valid CSRF token. It does not pass a request object, so
there is no session and no database access here. The template it renders is
standalone for the same reason.
"""

from django.template import loader
from django.http import HttpResponse


def csrf_failure(request, reason=""):
    """Explain the stale form and ask the user to reload.

    ``reason`` is Django's own explanation of the failure. It is never shown:
    it names cookies and tokens, which is no help to a student who left a tab
    open over lunch.

    The template is rendered without the request, so the context processors
    do not run. That matters: Django raises CSRF failures in middleware,
    before the session is loaded, and registration.context_processors
    .current_student reads request.session, which would raise AttributeError
    inside the error page itself.
    """
    return HttpResponse(
        loader.get_template("registration/errors/csrf.html").render(),
        status=403,
        content_type="text/html; charset=utf-8",
    )
