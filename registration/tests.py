import re
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import MAX_CREDIT_UNITS, Course, CourseType, Registration, Student

User = get_user_model()


class NoRawTemplateSyntaxTests(TestCase):
    """Rendered pages must never show template comment or tag syntax."""

    MARKERS = ["{#", "#}", "{%", "%}"]

    def assert_clean(self, client, url, label):
        response = client.get(url)
        if response.status_code == 302:
            response = client.get(response["Location"])
        self.assertEqual(response.status_code, 200, label)
        body = response.content.decode()
        for marker in self.MARKERS:
            with self.subTest(label=label, marker=marker):
                self.assertNotIn(marker, body)

    def test_public_pages_do_not_show_raw_template_syntax(self):
        staff = User.objects.create_user(
            username="staffer", password="staff-pass-123", is_staff=True
        )
        course = Course.objects.create(
            code="CSC101", title="Intro", level=100, credit_units=3
        )
        student = Student.objects.create(name="Amina Bello", level=100)
        session = self.client.session
        session["student_id"] = student.pk
        session.save()

        for name, label in [
            ("students:home", "identify"),
            ("students:course_selection", "selection"),
            ("students:my_courses", "my courses"),
            ("students:printable_form", "printable form"),
        ]:
            with self.subTest(page=label):
                self.assert_clean(self.client, reverse(name), label)

        self.assert_clean(Client(), reverse("registration:login"), "login")

        staff_client = Client()
        staff_client.force_login(staff)
        for name, args, label in [
            ("registration:home", (), "staff home"),
            ("registration:course_list", (), "course list"),
            ("registration:course_create", (), "course form"),
            ("registration:course_edit", (course.pk,), "edit course"),
            ("registration:student_list", (), "student list"),
            ("registration:student_detail", (student.pk,), "student detail"),
        ]:
            with self.subTest(page=label):
                self.assert_clean(staff_client, reverse(name, args=args), label)

    def test_template_files_do_not_open_an_inline_comment_left_unclosed(self):
        template_dir = Path(__file__).resolve().parent / "templates"
        for path in sorted(template_dir.rglob("*.html")):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                with self.subTest(path=path.name, line=number):
                    self.assertEqual("{#" in line, "#}" in line)


class StaffAccessTests(TestCase):
    """The /manage/ area is for signed-in staff only."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffer", password="staff-pass-123", is_staff=True
        )
        self.plain = User.objects.create_user(
            username="plain", password="plain-pass-123", is_staff=False
        )
        self.course = Course.objects.create(
            code="CSC101", title="Intro", level=100, credit_units=3
        )

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("registration:course_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("registration:login"), response["Location"])

    def test_signed_in_non_staff_gets_403(self):
        self.client.force_login(self.plain)
        for name in [
            "registration:home",
            "registration:course_list",
            "registration:course_create",
            "registration:student_list",
        ]:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_non_staff_cannot_toggle_a_course(self):
        self.client.force_login(self.plain)
        response = self.client.post(
            reverse("registration:course_toggle_active", args=[self.course.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_active)

    def test_toggle_rejects_get(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("registration:course_toggle_active", args=[self.course.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_active)

    def test_toggle_needs_a_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(
            reverse("registration:course_toggle_active", args=[self.course.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_active)

    def test_toggle_flips_the_course(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("registration:course_toggle_active", args=[self.course.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_active)

    def test_logout_rejects_get(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("registration:logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_needs_a_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(reverse("registration:logout"))
        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", client.session)

    def test_logout_ends_the_session(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("registration:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class StudentIdentificationTests(TestCase):
    """Students are matched on name plus level, ignoring case and spacing."""

    def identify(self, name, level=100, matric_no=""):
        return self.client.post(
            reverse("students:home"),
            {"name": name, "level": level, "matric_no": matric_no},
        )

    def test_name_is_trimmed_and_spaces_collapsed(self):
        self.identify("  amina   bello ")
        student = Student.objects.get()
        self.assertEqual(student.name, "amina bello")

    def test_name_keeps_the_capitalisation_the_student_typed(self):
        # Matching ignores case; the stored name is not rewritten.
        self.identify("Amina Bello")
        self.assertEqual(Student.objects.get().name, "Amina Bello")

    def test_same_name_and_level_reuses_the_record(self):
        self.identify("Amina Bello")
        self.identify("  AMINA   BELLO  ")
        self.assertEqual(Student.objects.count(), 1)

    def test_same_name_at_another_level_is_a_different_student(self):
        self.identify("Amina Bello", level=100)
        self.identify("Amina Bello", level=200)
        self.assertEqual(Student.objects.count(), 2)

    def test_matric_number_is_kept_and_filled_in_later(self):
        self.identify("Amina Bello")
        self.identify("Amina Bello", matric_no=" CSC/2026/001 ")
        self.assertEqual(Student.objects.get().matric_no, "CSC/2026/001")

    def test_blank_name_is_rejected(self):
        response = self.identify("   ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.count(), 0)

    def test_identifying_redirects_to_course_selection(self):
        response = self.identify("Amina Bello")
        self.assertRedirects(response, reverse("students:course_selection"))


class StudentCourseSelectionTests(TestCase):
    def setUp(self):
        self.course_a = Course.objects.create(
            code="PHY101", title="Mechanics", level=100, credit_units=3
        )
        self.course_b = Course.objects.create(
            code="PHY102", title="Electricity", level=100, credit_units=2
        )
        self.course_200 = Course.objects.create(
            code="PHY201", title="Waves", level=200, credit_units=3
        )
        self.inactive = Course.objects.create(
            code="PHY103", title="Retired", level=100, credit_units=3, is_active=False
        )
        self.student = Student.objects.create(name="Amina Bello", level=100)
        session = self.client.session
        session["student_id"] = self.student.pk
        session.save()

    def select(self, *courses):
        return self.client.post(
            reverse("students:course_selection"),
            {"courses": [course.pk for course in courses]},
        )

    def test_pages_require_identification(self):
        self.client.session.flush()
        response = self.client.get(reverse("students:course_selection"))
        self.assertRedirects(response, reverse("students:home"))

    def test_only_active_courses_at_the_students_level_are_offered(self):
        response = self.client.get(reverse("students:course_selection"))
        offered = {course.pk for course in response.context["courses"]}
        self.assertEqual(offered, {self.course_a.pk, self.course_b.pk})

    def test_selecting_courses_registers_them(self):
        response = self.select(self.course_a, self.course_b)
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(
            set(
                Registration.objects.filter(student=self.student).values_list(
                    "course_id", flat=True
                )
            ),
            {self.course_a.pk, self.course_b.pk},
        )

    def test_course_from_another_level_is_refused(self):
        response = self.select(self.course_200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not open to you")
        self.assertEqual(Registration.objects.count(), 0)

    def test_inactive_course_is_refused(self):
        response = self.select(self.inactive)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not open to you")
        self.assertEqual(Registration.objects.count(), 0)

    def test_credit_cap_is_enforced(self):
        heavy = [
            Course.objects.create(
                code=f"HVY{index}", title="Heavy", level=100, credit_units=5
            )
            for index in range(5)
        ]
        response = self.select(*heavy)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"The maximum is {MAX_CREDIT_UNITS}")
        self.assertEqual(Registration.objects.count(), 0)

    def test_exactly_the_cap_is_allowed(self):
        exact = [
            Course.objects.create(
                code=f"EXT{index}", title="Exact", level=100, credit_units=6
            )
            for index in range(4)
        ]
        response = self.select(*exact)
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(Registration.objects.count(), 4)

    def test_resubmitting_the_same_selection_does_not_duplicate(self):
        self.select(self.course_a)
        response = self.select(self.course_a)
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(Registration.objects.count(), 1)

    def test_running_total_is_shown(self):
        self.select(self.course_a, self.course_b)
        response = self.client.get(reverse("students:my_courses"))
        self.assertEqual(response.context["total_credit_units"], 5)

    def test_duplicate_course_ids_register_once(self):
        # The same course id posted twice must not add credit units twice.
        response = self.client.post(
            reverse("students:course_selection"),
            {"courses": [self.course_a.pk, self.course_a.pk]},
        )
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(Registration.objects.count(), 1)
        my_courses = self.client.get(reverse("students:my_courses"))
        self.assertEqual(my_courses.context["total_credit_units"], 3)

    def test_empty_submission_removes_everything(self):
        # Saving with nothing ticked means "take me off every course".
        self.select(self.course_a, self.course_b)
        self.assertEqual(Registration.objects.count(), 2)
        response = self.client.post(reverse("students:course_selection"), {})
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(Registration.objects.count(), 0)


class SelectiveSaveTests(TestCase):
    """Saving makes the registration equal the ticked set, in one go."""

    def setUp(self):
        self.course_a = Course.objects.create(
            code="PHY101", title="Mechanics", level=100, credit_units=3
        )
        self.course_b = Course.objects.create(
            code="PHY102", title="Electricity", level=100, credit_units=2
        )
        self.course_c = Course.objects.create(
            code="PHY103", title="Optics", level=100, credit_units=4
        )
        self.student = Student.objects.create(name="Amina Bello", level=100)
        session = self.client.session
        session["student_id"] = self.student.pk
        session.save()

    def select(self, *courses):
        return self.client.post(
            reverse("students:course_selection"),
            {"courses": [course.pk for course in courses]},
        )

    def registered_codes(self):
        return sorted(
            Registration.objects.filter(student=self.student).values_list(
                "course__code", flat=True
            )
        )

    def test_unticking_removes_the_course(self):
        self.select(self.course_a, self.course_b)
        self.select(self.course_a)
        self.assertEqual(self.registered_codes(), ["PHY101"])

    def test_add_and_remove_in_one_save(self):
        self.select(self.course_a, self.course_b)
        # Untick A, keep B, tick C: all in a single submit.
        self.select(self.course_b, self.course_c)
        self.assertEqual(self.registered_codes(), ["PHY102", "PHY103"])

    def test_saving_the_same_selection_says_no_changes(self):
        self.select(self.course_a, self.course_b)
        # Follow the redirect so the message stack is emptied before the retry.
        self.client.get(reverse("students:my_courses"))
        response = self.select(self.course_a, self.course_b)
        self.assertRedirects(response, reverse("students:my_courses"))
        stored = [str(message) for message in response.wsgi_request._messages]
        self.assertEqual(stored, ["No changes to save."])
        self.assertEqual(self.registered_codes(), ["PHY101", "PHY102"])

    def test_cap_applies_to_the_final_ticked_total(self):
        # A + B are 5 units. Adding C would make 9, so tick all three plus
        # enough heavy courses to pass 24 and the save must be refused.
        heavy = [
            Course.objects.create(
                code=f"BIG{index}", title="Big", level=100, credit_units=8
            )
            for index in range(3)
        ]
        response = self.select(self.course_a, self.course_b, *heavy)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That is 29 credit units")
        self.assertEqual(Registration.objects.count(), 0)

    def test_unticking_brings_a_selection_back_under_the_cap(self):
        # 23 units registered is fine; dropping one leaves 21, still fine.
        big = [
            Course.objects.create(
                code=f"CAP{index}", title="Cap", level=100, credit_units=8
            )
            for index in range(3)
        ]
        # 8 + 8 + 7 = 23
        small = Course.objects.create(
            code="SML101", title="Small", level=100, credit_units=7
        )
        self.select(big[0], big[1], small)
        self.assertEqual(Registration.objects.count(), 3)

        response = self.select(big[0], big[1])
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(self.registered_codes(), ["CAP0", "CAP1"])

    def test_select_page_renders_one_checkbox_per_course(self):
        # Regression: the page once rendered a table row plus a mobile card,
        # which put two boxes per course on the page and doubled the total.
        self.select(self.course_a, self.course_b)

        response = self.client.get(reverse("students:course_selection"))
        html = response.content.decode()

        ids = re.findall(r'name="courses"[^>]*?id="([^"]+)"', html)
        values = re.findall(r'<input[^>]*?name="courses"[^>]*?value="(\d+)"', html)

        self.assertEqual(len(values), len(set(values)), values)
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.assertEqual(len(values), 3)  # the three active 100 level courses

        # One label per input, and no duplicate or stale ids.
        for course in response.context["courses"]:
            self.assertEqual(values.count(str(course.pk)), 1)
            self.assertIn(f'id="course-{course.pk}"', html)
            self.assertIn(f'for="course-{course.pk}"', html)
            self.assertNotIn(f"course-card-{course.pk}", html)

    def test_initial_summary_matches_the_ticked_units(self):
        three = Course.objects.create(
            code="MTH201", title="Maths", level=100, credit_units=5
        )
        self.select(self.course_a, self.course_b, three)

        response = self.client.get(reverse("students:course_selection"))
        html = response.content.decode()

        ticked = re.findall(r'data-credit-units="(\d+)"[^>]*?checked', html)
        ticked_total = sum(int(value) for value in ticked)

        self.assertEqual(response.context["total_credit_units"], 3 + 2 + 5)
        self.assertEqual(len(ticked), 3)
        self.assertEqual(ticked_total, 10)
        self.assertEqual(response.context["selected_count"], 3)
        self.assertEqual(response.context["credit_percent"], 42)  # round(41.7)

        # Every output hook is present and carries the same initial number.
        self.assertEqual(html.count("data-credit-total-output"), 2)
        for value in re.findall(
            r"<span data-credit-total-output>(\d+)</span>", html
        ):
            self.assertEqual(int(value), 10)

    def test_failed_save_rolls_back_the_whole_selection(self):
        # Start from A + B. A submit that would exceed the cap must leave
        # the existing rows exactly as they were, no partial add or remove.
        self.select(self.course_a, self.course_b)
        before = self.registered_codes()

        heavy = [
            Course.objects.create(
                code=f"OVR{index}", title="Over", level=100, credit_units=9
            )
            for index in range(3)
        ]
        response = self.select(*heavy)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.registered_codes(), before)
        self.assertEqual(Registration.objects.count(), 2)

    def test_save_is_wrapped_in_a_transaction(self):
        # If the insert inside the block fails, the delete must be undone.
        from unittest.mock import patch

        from django.db import IntegrityError

        self.select(self.course_a, self.course_b)
        before = self.registered_codes()

        # Removing A and adding C, but force the insert to blow up.
        with patch(
            "registration.views.Registration.objects.create",
            side_effect=IntegrityError("boom"),
        ):
            with self.assertRaises(IntegrityError):
                self.select(self.course_b, self.course_c)

        # A was meant to be deleted; the rollback must have kept it.
        self.assertEqual(self.registered_codes(), before)


class CourseModelTests(TestCase):
    """Model level rules that the views rely on."""

    def test_duplicate_registration_is_rejected_by_the_database(self):
        from django.db import IntegrityError, transaction

        course = Course.objects.create(
            code="PHY101", title="Mechanics", level=100, credit_units=3
        )
        student = Student.objects.create(name="Amina Bello", level=100)
        Registration.objects.create(student=student, course=course)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Registration.objects.create(student=student, course=course)

        self.assertEqual(Registration.objects.filter(student=student).count(), 1)

    def test_course_code_is_normalised_to_uppercase(self):
        from .forms import CourseForm

        form = CourseForm(
            data={
                "code": "  csc101  ",
                "title": "Intro",
                "level": 100,
                "credit_units": 3,
                "course_type": CourseType.CORE,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().code, "CSC101")

    def test_duplicate_course_code_is_rejected(self):
        from .forms import CourseForm

        Course.objects.create(code="CSC101", title="Intro", level=100)
        form = CourseForm(
            data={
                "code": "csc101",
                "title": "Another",
                "level": 200,
                "credit_units": 3,
                "course_type": CourseType.CORE,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("code", form.errors)
        self.assertEqual(Course.objects.count(), 1)


class StaffCourseManagementTests(TestCase):
    """Staff create, edit and deactivate courses through /manage/."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffer", password="staff-pass-123", is_staff=True
        )
        self.client.force_login(self.staff)

    def test_staff_can_create_a_course(self):
        response = self.client.post(
            reverse("registration:course_create"),
            {
                "code": "csc101",
                "title": "Intro to Computing",
                "level": 100,
                "credit_units": 3,
                "course_type": CourseType.CORE,
            },
        )
        self.assertRedirects(response, reverse("registration:course_list"))
        course = Course.objects.get()
        self.assertEqual(course.code, "CSC101")
        self.assertEqual(course.title, "Intro to Computing")

    def test_staff_can_edit_a_course(self):
        course = Course.objects.create(
            code="CSC101", title="Intro", level=100, credit_units=3
        )
        response = self.client.post(
            reverse("registration:course_edit", args=[course.pk]),
            {
                "code": "CSC101",
                "title": "Introduction to Computing",
                "level": 200,
                "credit_units": 4,
                "course_type": CourseType.ELECTIVE,
            },
        )
        self.assertRedirects(response, reverse("registration:course_list"))
        course.refresh_from_db()
        self.assertEqual(course.title, "Introduction to Computing")
        self.assertEqual(course.level, 200)
        self.assertEqual(course.credit_units, 4)
        self.assertEqual(course.course_type, CourseType.ELECTIVE)


class DeactivationHidesCourseTests(TestCase):
    """A deactivated course disappears from the student selection page."""

    def setUp(self):
        self.course = Course.objects.create(
            code="PHY101", title="Mechanics", level=100, credit_units=3
        )
        self.student = Student.objects.create(name="Amina Bello", level=100)
        session = self.client.session
        session["student_id"] = self.student.pk
        session.save()

    def test_deactivation_removes_the_course_from_the_selection_page(self):
        before = self.client.get(reverse("students:course_selection"))
        self.assertContains(before, "PHY101")

        self.course.is_active = False
        self.course.save(update_fields=["is_active"])

        after = self.client.get(reverse("students:course_selection"))
        self.assertNotContains(after, "PHY101")
        self.assertEqual(after.context["courses"], [])


class StudentMyCoursesTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            code="PHY101", title="Mechanics", level=100, credit_units=3
        )
        self.student = Student.objects.create(name="Amina Bello", level=100)
        self.registration = Registration.objects.create(
            student=self.student, course=self.course
        )
        session = self.client.session
        session["student_id"] = self.student.pk
        session.save()

    def test_removing_a_course(self):
        response = self.client.post(
            reverse("students:remove_course", args=[self.registration.pk])
        )
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(Registration.objects.count(), 0)

    def test_remove_rejects_get(self):
        response = self.client.get(
            reverse("students:remove_course", args=[self.registration.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Registration.objects.count(), 1)

    def test_cannot_remove_another_students_registration(self):
        other = Student.objects.create(name="Bola Ade", level=100)
        theirs = Registration.objects.create(student=other, course=self.course)
        response = self.client.post(
            reverse("students:remove_course", args=[theirs.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Registration.objects.count(), 2)

    def test_start_over_forgets_the_student(self):
        response = self.client.post(reverse("students:start_over"))
        self.assertRedirects(response, reverse("students:home"))
        self.assertNotIn("student_id", self.client.session)


class StudentPrintableFormTests(TestCase):
    """The printable form is a formal document built from saved registrations."""

    def setUp(self):
        self.core = Course.objects.create(
            code="PHY101",
            title="Mechanics",
            level=100,
            credit_units=3,
            course_type=CourseType.CORE,
        )
        self.elective = Course.objects.create(
            code="PHY102",
            title="Electricity",
            level=100,
            credit_units=2,
            course_type=CourseType.ELECTIVE,
        )
        self.student = Student.objects.create(
            name="Amina Bello", level=100, matric_no="U20PH1234"
        )
        Registration.objects.create(student=self.student, course=self.core)
        Registration.objects.create(student=self.student, course=self.elective)
        session = self.client.session
        session["student_id"] = self.student.pk
        session.save()

    def get_form(self):
        return self.client.get(reverse("students:printable_form"))

    def test_heading_and_institution_name(self):
        response = self.get_form()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COURSE REGISTRATION FORM")
        self.assertContains(response, settings.INSTITUTION_NAME)

    def test_date_printed_is_todays_date(self):
        today = timezone.localdate()
        expected = f"{today.day} {today.strftime('%B')} {today.year}"
        response = self.get_form()
        self.assertContains(response, "Date printed")
        self.assertContains(response, expected)

    def test_student_details_are_shown(self):
        response = self.get_form()
        self.assertContains(response, "U20PH1234")
        self.assertContains(response, "Amina Bello")
        self.assertContains(response, "100 Level")

    def test_matric_number_falls_back_to_not_available(self):
        self.student.matric_no = ""
        self.student.save(update_fields=["matric_no"])
        response = self.get_form()
        self.assertContains(response, "N/A")

    def test_each_course_row_is_shown(self):
        response = self.get_form()
        self.assertContains(response, "PHY101")
        self.assertContains(response, "Mechanics")
        self.assertContains(response, "PHY102")
        self.assertContains(response, "Electricity")
        self.assertContains(response, "Core")
        self.assertContains(response, "Elective")

    def test_column_headings(self):
        response = self.get_form()
        self.assertContains(response, "Course Code")
        self.assertContains(response, "Course Title")
        self.assertContains(response, "Credit Units")
        self.assertContains(response, "Status")

    def test_total_credit_units_is_calculated(self):
        response = self.get_form()
        self.assertEqual(response.context["total_credit_units"], 5)
        self.assertContains(response, "Total Credit Units")

    def test_all_three_signature_labels(self):
        response = self.get_form()
        self.assertContains(response, "Student's Signature")
        self.assertContains(response, "Level Adviser's Signature")
        self.assertContains(response, "Faculty Officer's Signature")

    def test_no_approval_status_on_the_page(self):
        response = self.get_form()
        self.assertNotContains(response, "Approved")
        self.assertNotContains(response, "Approval")

    def test_redirects_when_no_student_in_session(self):
        self.client.session.flush()
        response = self.get_form()
        self.assertRedirects(response, reverse("students:home"))

    def test_student_b_cannot_see_student_a_form(self):
        other = Student.objects.create(
            name="Bola Ade", level=100, matric_no="U20PH9999"
        )
        session = self.client.session
        session["student_id"] = other.pk
        session.save()

        response = self.get_form()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bola Ade")
        self.assertContains(response, "U20PH9999")
        self.assertNotContains(response, "Amina Bello")
        self.assertNotContains(response, "U20PH1234")
        self.assertNotContains(response, "PHY101")


class SeedDataCommandTests(TestCase):
    """The sample data command is safe to repeat and leaves staff alone."""

    def run_seed(self):
        call_command("seed_data", stdout=StringIO())

    def test_courses_cover_all_five_levels_with_both_types(self):
        self.run_seed()
        self.assertEqual(
            set(Course.objects.values_list("level", flat=True)),
            {100, 200, 300, 400, 500},
        )
        self.assertEqual(
            set(Course.objects.values_list("course_type", flat=True)),
            {CourseType.CORE, CourseType.ELECTIVE},
        )

    def test_two_students_have_registrations(self):
        self.run_seed()
        self.assertEqual(Student.objects.count(), 2)
        for student in Student.objects.all():
            self.assertGreater(student.registrations.count(), 0)

    def test_students_are_registered_within_the_credit_cap(self):
        self.run_seed()
        for student in Student.objects.all():
            total = sum(
                registration.course.credit_units
                for registration in student.registrations.select_related("course")
            )
            self.assertLessEqual(total, MAX_CREDIT_UNITS)

    def test_students_only_hold_courses_at_their_own_level(self):
        self.run_seed()
        for student in Student.objects.all():
            levels = set(
                student.registrations.values_list("course__level", flat=True)
            )
            self.assertEqual(levels, {student.level})

    def test_running_twice_changes_nothing(self):
        self.run_seed()
        first = (
            Course.objects.count(),
            Student.objects.count(),
            Registration.objects.count(),
        )
        self.run_seed()
        second = (
            Course.objects.count(),
            Student.objects.count(),
            Registration.objects.count(),
        )
        self.assertEqual(first, second)
        self.assertEqual(second, (15, 2, 6))

    def test_staff_accounts_are_not_created_or_changed(self):
        staff = User.objects.create_user(
            username="admin", password="secret123", is_staff=True
        )
        before = (
            User.objects.count(),
            staff.pk,
            staff.username,
            staff.password,
            staff.is_staff,
            staff.is_superuser,
            staff.is_active,
            staff.last_login,
        )

        self.run_seed()

        staff.refresh_from_db()
        after = (
            User.objects.count(),
            staff.pk,
            staff.username,
            staff.password,
            staff.is_staff,
            staff.is_superuser,
            staff.is_active,
            staff.last_login,
        )
        self.assertEqual(before, after)
        self.assertEqual(User.objects.count(), 1)
