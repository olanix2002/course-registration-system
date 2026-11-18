from django.http import HttpResponse
from django.template import loader


def _render(template_name, status):
    """Render an error page without a request, so no context processor runs."""
    return HttpResponse(
        loader.get_template(template_name).render(),
        status=status,
        content_type="text/html; charset=utf-8",
    )


def bad_request(request, exception=None):
    return _render("registration/errors/400.html", 400)


def permission_denied(request, exception=None):
    return _render("registration/errors/403.html", 403)


def page_not_found(request, exception=None):
    return _render("registration/errors/404.html", 404)


def server_error(request):
    return _render("registration/errors/500.html", 500)


def csrf_failure(request, reason=""):
    """Explain the stale form and ask the user to reload.

    ``reason`` is Django's own explanation of the failure. It is never shown:
    it names cookies and tokens, which is no help to a student who left a tab
    open over lunch.

    The template is rendered without the request, so the context processors
    do not run. Django raises CSRF failures in middleware, before the session
    is loaded, and registration.context_processors.current_student reads
    request.session, which would raise AttributeError inside the error page.
    """
    return _render("registration/errors/csrf.html", 403)
