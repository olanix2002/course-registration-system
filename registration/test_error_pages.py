"""Tests for the standalone error pages and the CSRF failure page."""

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.signals import template_rendered
from django.urls import reverse

from registration import error_views


class ErrorPageTests(TestCase):
    def test_request_errors_log_to_stdout(self):
        logger = settings.LOGGING["loggers"]["django.request"]
        self.assertEqual(logger["level"], "ERROR")
        self.assertEqual(logger["handlers"], ["stdout"])
        handler = settings.LOGGING["handlers"]["stdout"]
        self.assertEqual(handler["class"], "logging.StreamHandler")
        self.assertEqual(handler["stream"], "ext://sys.stdout")

    @override_settings(DEBUG=False)
    def test_404_page_renders(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "registration/errors/404.html")
        self.assertContains(response, "We could not find that page", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)

    @override_settings(DEBUG=False)
    def test_403_page_renders_for_non_staff(self):
        user = User.objects.create_user(username="notstaff", password="pass-123")
        self.client.force_login(user)
        response = self.client.get(reverse("registration:course_list"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "registration/errors/403.html")
        self.assertContains(response, "You do not have access to this page", status_code=403)

    def test_csrf_failure_page_renders(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("registration:logout"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "registration/errors/csrf.html")
        self.assertContains(response, "This page was open too long", status_code=403)
        self.assertContains(response, "Reload the page", status_code=403)

    def test_error_pages_need_no_database_or_request_context(self):
        factory = RequestFactory()
        request = factory.get("/boom/")
        cases = [
            (error_views.bad_request, 400, "registration/errors/400.html"),
            (error_views.permission_denied, 403, "registration/errors/403.html"),
            (error_views.page_not_found, 404, "registration/errors/404.html"),
            (error_views.server_error, 500, "registration/errors/500.html"),
            (error_views.csrf_failure, 403, "registration/errors/csrf.html"),
        ]
        seen = []

        def record(sender, template, context, **kwargs):
            if template.name:
                seen.append(template.name)

        template_rendered.connect(record)
        try:
            for view, status, template in cases:
                with self.subTest(view=view.__name__), self.assertNumQueries(0):
                    seen.clear()
                    response = view(request)
                    self.assertEqual(response.status_code, status)
                    self.assertIn(template, seen)
                    self.assertNotIn(b"{#", response.content)
                    self.assertNotIn(b"{%", response.content)
        finally:
            template_rendered.disconnect(record)
