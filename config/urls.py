"""Top-level URL configuration.

The staff area lives under /manage/ (see registration/urls.py). Django's own
admin site is kept, but moved to /django-admin/ so the two never collide.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("manage/", include("registration.urls")),
]
