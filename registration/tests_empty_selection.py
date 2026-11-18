"""Regression tests for saving a selection in which every course is unticked.

Unticking everything is a legal, meaningful action: it withdraws the whole
registration. These tests pin that down so it cannot start returning an
error page again.
"""

from django.test import TestCase
from django.urls import reverse

from .models import STUDENT_SESSION_KEY, Course, Level, Registration, Student


class EmptySelectionTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(name="Amina Bello", level=Level.LEVEL_100)
        self.courses = [
            Course.objects.create(
                code=f"CSC{index}01",
                title=f"Course {index}",
                level=Level.LEVEL_100,
                credit_units=3,
            )
            for index in (1, 2, 3)
        ]
        for course in self.courses[:2]:
            Registration.objects.create(student=self.student, course=course)
        session = self.client.session
        session[STUDENT_SESSION_KEY] = self.student.pk
        session.save()

    def _pages(self):
        return [
            reverse("students:course_selection"),
            reverse("students:my_courses"),
            reverse("students:printable_form"),
        ]

    def test_unticking_every_course_clears_the_selection(self):
        response = self.client.post(reverse("students:course_selection"), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Registration.objects.filter(student=self.student).count(), 0)

    def test_pages_render_after_every_course_is_unticked(self):
        self.client.post(reverse("students:course_selection"), {})
        for url in self._pages():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_empty_save_with_no_registrations_is_a_no_op(self):
        Registration.objects.filter(student=self.student).delete()
        response = self.client.post(reverse("students:course_selection"), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Registration.objects.filter(student=self.student).count(), 0)

    def test_empty_save_reports_removals(self):
        response = self.client.post(
            reverse("students:course_selection"), {}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        messages = [str(message) for message in response.context["messages"]]
        self.assertTrue(
            any("removed" in message.lower() for message in messages), messages
        )
