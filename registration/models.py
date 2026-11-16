from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class Level(models.IntegerChoices):
    LEVEL_100 = 100, "100 Level"
    LEVEL_200 = 200, "200 Level"
    LEVEL_300 = 300, "300 Level"
    LEVEL_400 = 400, "400 Level"
    LEVEL_500 = 500, "500 Level"


class CourseType(models.TextChoices):
    CORE = "Core", "Core"
    ELECTIVE = "Elective", "Elective"


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    level = models.PositiveSmallIntegerField(choices=Level.choices)
    credit_units = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
    )
    course_type = models.CharField(
        max_length=10,
        choices=CourseType.choices,
        default=CourseType.CORE,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["level", "code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(level__in=Level.values),
                name="course_level_is_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_units__gte=1),
                name="course_credit_units_are_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(course_type__in=CourseType.values),
                name="course_type_is_valid",
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.title}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Courses cannot be deleted. Deactivate them instead.")


class Student(models.Model):
    name = models.CharField(max_length=150)
    level = models.PositiveSmallIntegerField(choices=Level.choices)
    matric_no = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "level"]
        constraints = [
            # The same person is matched by name, ignoring case, plus level.
            models.UniqueConstraint(
                Lower("name"),
                "level",
                name="unique_student_name_and_level",
            ),
            models.CheckConstraint(
                condition=models.Q(level__in=Level.values),
                name="student_level_is_valid",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"


class Registration(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="registrations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["course__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course",
            ),
        ]

    def __str__(self):
        return f"{self.student.name} — {self.course.code}"
