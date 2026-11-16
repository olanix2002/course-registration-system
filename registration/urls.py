from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import StaffLoginForm

app_name = "registration"

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/manage/login.html",
            authentication_form=StaffLoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("courses/", views.course_list, name="course_list"),
    path("courses/new/", views.course_create, name="course_create"),
    path("courses/<int:pk>/edit/", views.course_edit, name="course_edit"),
    path(
        "courses/<int:pk>/toggle/",
        views.course_toggle_active,
        name="course_toggle_active",
    ),
    path("students/", views.student_list, name="student_list"),
    path("students/<int:pk>/", views.student_detail, name="student_detail"),
]
