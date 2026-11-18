"""Top-level URL configuration.

/            student pages (registration/student_urls.py)
/manage/     staff area       (registration/urls.py)
/django-admin/  Django's own admin, moved so it never collides with /manage/
"""

from django.contrib import admin
from django.urls import include, path

# Django calls these four hooks for 400, 403, 404 and 500 responses when DEBUG
# is False. Each one renders a standalone template from
# registration/templates/registration/errors/, so the pages need no database
# and no context processor. Without the hooks Django would show its bare
# built-in pages in production.
handler400 = "registration.error_views.bad_request"
handler403 = "registration.error_views.permission_denied"
handler404 = "registration.error_views.page_not_found"
handler500 = "registration.error_views.server_error"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("manage/", include("registration.urls")),
    path("", include("registration.student_urls")),
]
