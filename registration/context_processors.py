from django.conf import settings


def institution(request):
    """Expose the institution name to every template (navbar and printable form)."""
    return {"INSTITUTION_NAME": settings.INSTITUTION_NAME}
