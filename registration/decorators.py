from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """Restrict a view to signed-in staff accounts.

    Visitors who are not signed in are sent to the staff login page, and the
    page they asked for is kept in ``?next=`` so they land on it afterwards.
    Signed-in users who are not staff get a 403 Forbidden response.
    """

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
