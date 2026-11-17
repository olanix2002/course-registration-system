from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Course, Level, Student, normalise_name


class StaffLoginForm(AuthenticationForm):
    """The standard Django login form, styled with Bootstrap classes."""

    # One short line, whatever the underlying reason was. Django uses the
    # same message for an unknown user and a bad password on purpose.
    error_messages = {
        "invalid_login": "Incorrect username or password.",
        "inactive": "Incorrect username or password.",
    }

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


class StudentIdentifyForm(forms.Form):
    """Identify the student using the public pages.

    Students do not have accounts. They give a name and level, and the same
    name at the same level always resolves to the same record, so a student
    who comes back sees the courses they already registered for.
    """

    name = forms.CharField(
        max_length=150,
        label="Full name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autofocus": True,
                "placeholder": "e.g. Amina Bello",
            }
        ),
    )
    level = forms.TypedChoiceField(
        choices=Level.choices,
        coerce=int,
        label="Level",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    matric_no = forms.CharField(
        max_length=30,
        required=False,
        label="Matriculation number",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Optional"}
        ),
    )

    def clean_name(self):
        # "  amina   bello " and "Amina Bello" must be the same student.
        name = normalise_name(self.cleaned_data["name"])
        if not name:
            raise forms.ValidationError("Enter your full name.")
        return name

    def clean_matric_no(self):
        return normalise_name(self.cleaned_data["matric_no"])

    def save(self):
        """Return the matching student, creating the record on first visit."""
        name = self.cleaned_data["name"]
        level = self.cleaned_data["level"]
        matric_no = self.cleaned_data["matric_no"]

        student, created = Student.objects.get_or_create(
            name__iexact=name,
            level=level,
            defaults={"name": name, "matric_no": matric_no},
        )
        if not created and matric_no and not student.matric_no:
            student.matric_no = matric_no
            student.save(update_fields=["matric_no"])
        return student
