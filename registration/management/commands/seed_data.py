"""Create sample courses, students and registrations for a demo.

Every record is looked up before it is created, so running the command a
second time changes nothing. Staff accounts are never read or written here.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from registration.models import Course, CourseType, Registration, Student

# code, title, level, credit units, course type
COURSES = [
    ("MTH101", "Elementary Mathematics I", 100, 3, CourseType.CORE),
    ("CHM101", "General Chemistry I", 100, 3, CourseType.CORE),
    ("GST101", "Communication in English", 100, 2, CourseType.ELECTIVE),
    ("MTH201", "Mathematical Methods I", 200, 3, CourseType.CORE),
    ("CHM201", "Organic Chemistry I", 200, 3, CourseType.CORE),
    ("CSC201", "Introduction to Programming", 200, 2, CourseType.ELECTIVE),
    ("MTH301", "Real Analysis", 300, 3, CourseType.CORE),
    ("CHM301", "Physical Chemistry", 300, 3, CourseType.CORE),
    ("STA301", "Probability Theory", 300, 2, CourseType.ELECTIVE),
    ("MTH401", "Abstract Algebra", 400, 3, CourseType.CORE),
    ("CHM401", "Instrumental Analysis", 400, 3, CourseType.CORE),
    ("CSC401", "Database Systems", 400, 2, CourseType.ELECTIVE),
    ("MTH501", "Functional Analysis", 500, 3, CourseType.CORE),
    ("CHM501", "Advanced Spectroscopy", 500, 3, CourseType.CORE),
    ("CSC501", "Software Engineering", 500, 2, CourseType.ELECTIVE),
]

# name, level, matric number, course codes to register
STUDENTS = [
    ("Amina Bello", 100, "U20CH1001", ["MTH101", "CHM101", "GST101"]),
    ("Bola Ade", 300, "U20CH3002", ["MTH301", "CHM301", "STA301"]),
]


class Command(BaseCommand):
    help = "Create sample courses, students and registrations."

    @transaction.atomic
    def handle(self, *args, **options):
        courses_created = 0
        for code, title, level, credit_units, course_type in COURSES:
            _, created = Course.objects.get_or_create(
                code=code,
                defaults={
                    "title": title,
                    "level": level,
                    "credit_units": credit_units,
                    "course_type": course_type,
                },
            )
            courses_created += created

        students_created = 0
        registrations_created = 0
        for name, level, matric_no, course_codes in STUDENTS:
            student, created = Student.objects.get_or_create(
                name__iexact=name,
                level=level,
                defaults={"name": name, "matric_no": matric_no},
            )
            students_created += created

            for code in course_codes:
                course = Course.objects.get(code=code)
                _, made = Registration.objects.get_or_create(
                    student=student,
                    course=course,
                )
                registrations_created += made

        self.stdout.write(
            f"Courses created: {courses_created} "
            f"(total {Course.objects.count()})"
        )
        self.stdout.write(
            f"Students created: {students_created} "
            f"(total {Student.objects.count()})"
        )
        self.stdout.write(
            f"Registrations created: {registrations_created} "
            f"(total {Registration.objects.count()})"
        )
        self.stdout.write(self.style.SUCCESS("Sample data is ready."))
