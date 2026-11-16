from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Course


class StaffLoginForm(AuthenticationForm):
    """The standard Django login form, styled with Bootstrap classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update({"class": "form-control"})


class CourseForm(forms.ModelForm):
    """Create or edit a course.

    A course is never deleted; activation is handled by a separate button on
    the course list, so ``is_active`` is not part of this form.
    """

    class Meta:
        model = Course
        fields = ["code", "title", "level", "credit_units", "course_type"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "level": forms.Select(attrs={"class": "form-select"}),
            "credit_units": forms.NumberInput(attrs={"class": "form-control"}),
            "course_type": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_code(self):
        # Store course codes in one consistent form: "phy 101 " -> "PHY 101".
        code = self.cleaned_data["code"].strip().upper()
        if not code:
            raise forms.ValidationError("Enter a course code.")
        return code
