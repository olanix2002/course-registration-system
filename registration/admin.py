from django.contrib import admin

from .models import Course, Registration, Student


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "level",
        "credit_units",
        "course_type",
        "is_active",
    )
    list_filter = ("level", "course_type", "is_active")
    search_fields = ("code", "title")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "matric_no", "created_at")
    list_filter = ("level",)
    search_fields = ("name", "matric_no")


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "created_at")
