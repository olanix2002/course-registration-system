from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import staff_required
from .forms import CourseForm, StudentIdentifyForm
from .models import (
    MAX_CREDIT_UNITS,
    STUDENT_SESSION_KEY,
    Course,
    Level,
    Registration,
    Student,
)

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


# ---------------------------------------------------------------------------
# Student flow. Students have no accounts: they identify themselves by name and
# level, and the id of the matching Student record is kept in the session.
# ---------------------------------------------------------------------------


def _current_student(request):
    """The student using the public pages, or None."""
    pk = request.session.get(STUDENT_SESSION_KEY)
    if not pk:
        return None
    return Student.objects.filter(pk=pk).first()


def _student_or_redirect(request):
    """Return (student, None), or (None, redirect) when nobody is identified."""
    student = _current_student(request)
    if student is None:
        return None, redirect("students:home")
    return student, None


def _registered_courses(student):
    """Map course id -> course for everything the student has registered."""
    return {
        registration.course_id: registration.course
        for registration in student.registrations.select_related("course")
    }


def student_home(request):
    """Identify the student, then send them to course selection."""
    if request.method == "POST":
        form = StudentIdentifyForm(request.POST)
        if form.is_valid():
            student = form.save()
            request.session[STUDENT_SESSION_KEY] = student.pk
            return redirect("students:course_selection")
    else:
        if _current_student(request) is not None:
            return redirect("students:course_selection")
        form = StudentIdentifyForm()
    return render(request, "registration/student/identify.html", {"form": form})


def student_course_selection(request):
    """Offer the active courses at the student's level and save the ticked set.

    Saving replaces the student's whole selection: newly ticked courses are
    added, courses that were unticked are removed, and both happen in one
    transaction so the student never ends up with a half-applied selection.
    """
    student, response = _student_or_redirect(request)
    if response is not None:
        return response

    courses = list(Course.objects.filter(is_active=True, level=student.level))
    registered = _registered_courses(student)
    registered_ids = set(registered)
    offered = {course.pk for course in courses}
    selected_ids = registered_ids
    error = None

    if request.method == "POST":
        try:
            submitted = {int(value) for value in request.POST.getlist("courses")}
        except (TypeError, ValueError):
            submitted = None

        if submitted is None:
            error = "That selection could not be read. Please try again."
        elif not submitted <= offered:
            # Covers courses at another level and deactivated courses.
            selected_ids = submitted
            error = "One or more of those courses is not open to you."
        else:
            selected_ids = submitted
            to_add = submitted - registered_ids
            to_remove = registered_ids - submitted
            total = sum(
                course.credit_units for pk, course in registered.items()
                if pk in submitted
            ) + sum(
                course.credit_units for course in courses
                if course.pk in to_add
            )

            if total > MAX_CREDIT_UNITS:
                error = (
                    f"That is {total} credit units. "
                    f"The maximum is {MAX_CREDIT_UNITS}."
                )
            elif not to_add and not to_remove:
                messages.info(request, "No changes to save.")
                return redirect("students:my_courses")
            else:
                with transaction.atomic():
                    if to_remove:
                        Registration.objects.filter(
                            student=student, course_id__in=to_remove
                        ).delete()
                    for course_id in to_add:
                        Registration.objects.create(
                            student=student, course_id=course_id
                        )
                parts = []
                if to_add:
                    parts.append(f"{len(to_add)} added")
                if to_remove:
                    parts.append(f"{len(to_remove)} removed")
                messages.success(
                    request,
                    "Registration saved: " + ", ".join(parts) + ".",
                )
                return redirect("students:my_courses")

    total_credit_units = sum(
        course.credit_units
        for pk, course in registered.items()
        if pk in selected_ids
    ) + sum(
        course.credit_units
        for course in courses
        if course.pk in selected_ids and course.pk not in registered_ids
    )

    context = {
        "student": student,
        "courses": courses,
        "registered_ids": registered_ids,
        "selected_ids": selected_ids,
        "total_credit_units": total_credit_units,
        "max_credit_units": MAX_CREDIT_UNITS,
        # Initial values. They match what the script computes from the ticked
        # boxes, so the page does not flicker on load.
        "selected_count": len(selected_ids),
        "credit_percent": min(
            100, round(total_credit_units / MAX_CREDIT_UNITS * 100)
        ),
        "error": error,
    }
    return render(request, "registration/student/select.html", context)


def student_my_courses(request):
    """Everything the student is registered for, with the running total."""
    student, response = _student_or_redirect(request)
    if response is not None:
        return response

    registrations = list(student.registrations.select_related("course"))
    total_credit_units = sum(
        registration.course.credit_units for registration in registrations
    )
    context = {
        "student": student,
        "registrations": registrations,
        "total_credit_units": total_credit_units,
        "max_credit_units": MAX_CREDIT_UNITS,
        "credit_percent": min(
            100, round(total_credit_units / MAX_CREDIT_UNITS * 100)
        ),
    }
    return render(request, "registration/student/my_courses.html", context)


@require_POST
def student_remove_course(request, pk):
    """Drop one of the student's own registrations."""
    student, response = _student_or_redirect(request)
    if response is not None:
        return response

    registration = get_object_or_404(Registration, pk=pk, student=student)
    code = registration.course.code
    registration.delete()
    messages.success(request, f"{code} was removed from your registration.")
    return redirect("students:my_courses")


def student_printable_form(request):
    """A print-ready copy of the student's registration."""
    student, response = _student_or_redirect(request)
    if response is not None:
        return response

    registrations = list(student.registrations.select_related("course"))
    context = {
        "student": student,
        "registrations": registrations,
        # Totalled here, never stored on the student or the registration.
        "total_credit_units": sum(
            registration.course.credit_units for registration in registrations
        ),
        "printed_on": timezone.localdate(),
    }
    return render(request, "registration/student/print.html", context)


@require_POST
def student_start_over(request):
    """Forget the identified student, e.g. when the next person uses the page."""
    request.session.pop(STUDENT_SESSION_KEY, None)
    return redirect("students:home")
