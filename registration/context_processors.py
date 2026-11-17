from django.conf import settings

from .models import STUDENT_SESSION_KEY, Student


def institution(request):
    """Expose the institution name to every template (navbar and printable form)."""
    return {"INSTITUTION_NAME": settings.INSTITUTION_NAME}


def current_student(request):
    """Expose the student using the public pages, so the navbar can show them."""
    pk = request.session.get(STUDENT_SESSION_KEY)
    if not pk:
        return {"current_student": None}
    return {"current_student": Student.objects.filter(pk=pk).first()}
