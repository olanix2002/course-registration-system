from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import MAX_CREDIT_UNITS, Course, CourseType, Registration, Student

User = get_user_model()


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

    def test_registering_twice_does_not_duplicate(self):
        self.select(self.course_a)
        self.select(self.course_a)
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

    def test_empty_submission_is_accepted_and_registers_nothing(self):
        # The selection page is additive, so no tick boxes means no change.
        response = self.client.post(reverse("students:course_selection"), {})
        self.assertRedirects(response, reverse("students:my_courses"))
        self.assertEqual(Registration.objects.count(), 0)


class AdditiveSubmissionTests(TestCase):
    """Submitting the selection page again adds to the old selection."""

    def setUp(self):
        self.course_a = Course.objects.create(
            code="PHY101", title="Mechanics", level=100, credit_units=3
        )
        self.course_b = Course.objects.create(
            code="PHY102", title="Electricity", level=100, credit_units=2
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

    def test_second_submission_keeps_the_first_selection(self):
        self.select(self.course_a)
        self.select(self.course_b)
        self.assertEqual(self.registered_codes(), ["PHY101", "PHY102"])

    def test_cap_counts_units_already_registered(self):
        # 20 units already held, plus 5 more, is over the 24 unit cap.
        held = [
            Course.objects.create(
                code=f"HLD{index}", title="Held", level=100, credit_units=5
            )
            for index in range(4)
        ]
        self.select(*held)
        self.assertEqual(Registration.objects.count(), 4)

        extra = Course.objects.create(
            code="XTRA1", title="Extra", level=100, credit_units=5
        )
        response = self.select(extra)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "That would bring you to 25 credit units")
        self.assertNotIn("XTRA1", self.registered_codes())
        self.assertEqual(Registration.objects.count(), 4)


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
