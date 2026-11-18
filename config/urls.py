"""Top-level URL configuration.

/            student pages (registration/student_urls.py)
/manage/     staff area       (registration/urls.py)
/django-admin/  Django's own admin, moved so it never collides with /manage/
"""

from django.contrib import admin
from django.urls import include, path

# These four names are what make Django render the templates in
# registration/templates/registration/errors/ for 400, 403, 404 and 500.
# A URLconf with none of its own handler400/403/404/500 falls back to Django's
# bare built-in pages, which is what happens in production where DEBUG is False.
handler400 = "django.views.defaults.bad_request"
handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("manage/", include("registration.urls")),
    path("", include("registration.student_urls")),
]
