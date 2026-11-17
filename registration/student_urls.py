"""Public, student-facing URLs. These live at the site root, not under /manage/."""

from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.student_home, name="home"),
    path("courses/", views.student_course_selection, name="course_selection"),
    path("my-courses/", views.student_my_courses, name="my_courses"),
    path(
        "my-courses/print/",
        views.student_printable_form,
        name="printable_form",
    ),
    path(
        "my-courses/<int:pk>/remove/",
        views.student_remove_course,
        name="remove_course",
    ),
    path("start-over/", views.student_start_over, name="start_over"),
]
