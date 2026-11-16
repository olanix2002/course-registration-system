from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .decorators import staff_required
from .forms import CourseForm
from .models import Course, Level, Student

# The level values accepted in query strings, e.g. {"100", "200", ...}.
VALID_LEVELS = {str(value) for value in Level.values}


def _clean_level(raw):
    """Return a valid level as a string, or "" when the value is not a level."""
    level = (raw or "").strip()
    return level if level in VALID_LEVELS else ""


@staff_required
def home(request):
    """The staff area has no dashboard of its own; start at the course list."""
    return redirect("registration:course_list")


@staff_required
def course_list(request):
    level = _clean_level(request.GET.get("level"))
    courses = Course.objects.all()
    if level:
        courses = courses.filter(level=int(level))
    context = {
        "courses": courses,
        "levels": Level.choices,
        "selected_level": level,
    }
    return render(request, "registration/manage/course_list.html", context)


@staff_required
def course_create(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(request, f"Course {course.code} was created.")
            return redirect("registration:course_list")
    else:
        form = CourseForm()
    return render(
        request,
        "registration/manage/course_form.html",
        {"form": form, "heading": "New course"},
    )


@staff_required
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            course = form.save()
            messages.success(request, f"Course {course.code} was updated.")
            return redirect("registration:course_list")
    else:
        form = CourseForm(instance=course)
    return render(
        request,
        "registration/manage/course_form.html",
        {"form": form, "heading": f"Edit {course.code}", "course": course},
    )


@staff_required
@require_POST
def course_toggle_active(request, pk):
    """Flip a course between active and inactive. Courses are never deleted."""
    course = get_object_or_404(Course, pk=pk)
    course.is_active = not course.is_active
    course.save(update_fields=["is_active"])
    state = "activated" if course.is_active else "deactivated"
    messages.success(request, f"Course {course.code} was {state}.")

    # Keep the level filter the staff member was looking at.
    level = _clean_level(request.POST.get("level"))
    target = reverse("registration:course_list")
    if level:
        target = f"{target}?level={level}"
    return redirect(target)


@staff_required
def student_list(request):
    query = " ".join(request.GET.get("q", "").split())
    level = _clean_level(request.GET.get("level"))

    students = Student.objects.annotate(course_count=Count("registrations"))
    if query:
        students = students.filter(name__icontains=query)
    if level:
        students = students.filter(level=int(level))

    context = {
        "students": students,
        "levels": Level.choices,
        "query": query,
        "selected_level": level,
    }
    return render(request, "registration/manage/student_list.html", context)


@staff_required
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    registrations = student.registrations.select_related("course")
    total_credit_units = sum(item.course.credit_units for item in registrations)
    context = {
        "student": student,
        "registrations": registrations,
        "total_credit_units": total_credit_units,
    }
    return render(request, "registration/manage/student_detail.html", context)
