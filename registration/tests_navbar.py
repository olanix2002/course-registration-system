"""Which navbar each section shows.

The navbar is chosen by section, not by who is signed in:
student pages carry the student navbar, the staff sign-in page carries the
brand alone, and the rest of /manage/ carries the staff navbar. A staff
account on a student page gets one quiet link back to the staff area.

The markup these tests read lives in registration/templates/registration/
base.html: the student navbar opens at line 25, the login-only brand bar at
line 67 and the staff navbar at line 75.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Course, Registration, Student

User = get_user_model()


class NavbarBySectionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffer", password="staff-pass-123", is_staff=True
        )
        self.course = Course.objects.create(
            code="CSC101", title="Intro", level=100, credit_units=3
        )
        self.student = Student.objects.create(name="Amina Bello", level=100)
        Registration.objects.create(student=self.student, course=self.course)

    def nav(self, response):
        """The navbar markup of a page, from <nav> to its closing tag."""
        html = response.content.decode()
        start = html.index("<nav")
        end = html.index("</nav>") + len("</nav>")
        return html[start:end]

    def identify(self, client, name="Amina Bello", level=100):
        session = client.session
        student = Student.objects.filter(name=name, level=level).first()
        session["student_id"] = student.pk
        session.save()

    def test_student_pages_show_the_student_navbar(self):
        self.identify(self.client)
        nav = self.nav(self.client.get(reverse("students:course_selection")))
        self.assertIn("Select courses", nav)
        self.assertIn("My courses", nav)
        self.assertNotIn("Sign out", nav)
        # The brand on a student page leads back into the student flow.
        self.assertIn(reverse("students:course_selection"), nav)

    def test_student_navbar_has_no_staff_link_for_a_student(self):
        self.identify(self.client)
        nav = self.nav(self.client.get(reverse("students:course_selection")))
        self.assertNotIn("Staff area", nav)

    def test_staff_account_on_a_student_page_gets_one_link_back(self):
        self.identify(self.client)
        self.client.force_login(self.staff)
        nav = self.nav(self.client.get(reverse("students:course_selection")))
        self.assertIn("Staff area", nav)
        self.assertIn(reverse("registration:course_list"), nav)
        # Still the student navbar, not the staff one.
        self.assertNotIn("Sign out", nav)

    def test_staff_navbar_is_unchanged_on_manage_pages(self):
        self.client.force_login(self.staff)
        nav = self.nav(self.client.get(reverse("registration:course_list")))
        self.assertIn("Courses", nav)
        self.assertIn("Students", nav)
        self.assertIn("Sign out", nav)
        self.assertNotIn("Select courses", nav)

    def test_login_page_shows_the_brand_alone(self):
        nav = self.nav(self.client.get(reverse("registration:login")))
        self.assertIn("navbar-brand", nav)
        self.assertNotIn("Select courses", nav)
        self.assertNotIn("Sign out", nav)
        # No menu, so no toggle button to open one.
        self.assertNotIn("navbar-toggler", nav)

    def test_active_link_follows_the_current_student_page(self):
        self.identify(self.client)
        select_nav = self.nav(self.client.get(reverse("students:course_selection")))
        my_nav = self.nav(self.client.get(reverse("students:my_courses")))
        print_nav = self.nav(self.client.get(reverse("students:printable_form")))
        self.assertIn('nav-link active" href="%s"' % reverse(
            "students:course_selection"
        ), select_nav)
        self.assertIn('nav-link active" href="%s"' % reverse(
            "students:my_courses"
        ), my_nav)
        # The printable form is part of "My courses".
        self.assertIn('nav-link active" href="%s"' % reverse(
            "students:my_courses"
        ), print_nav)

    def test_student_chip_shows_name_and_level(self):
        self.identify(self.client)
        nav = self.nav(self.client.get(reverse("students:course_selection")))
        self.assertIn("Amina Bello", nav)
        self.assertIn("user-chip", nav)
        self.assertIn("Not you?", nav)

    def test_staff_without_a_student_sees_no_chip_on_the_identify_page(self):
        self.client.force_login(self.staff)
        nav = self.nav(self.client.get(reverse("students:home")))
        self.assertIn("Staff area", nav)
        self.assertNotIn("user-chip", nav)
