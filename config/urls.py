"""Top-level URL configuration.

/            student pages (registration/student_urls.py)
/manage/     staff area       (registration/urls.py)
/django-admin/  Django's own admin, moved so it never collides with /manage/
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("manage/", include("registration.urls")),
    path("", include("registration.student_urls")),
]
