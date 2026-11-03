from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from races.models import Season
from sx5_project.tests.test_race_file_upload import generate_file_with_runners


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class TestServerErrorPage(TestCase):
    # Uploading a race for a season that doesn't exist raises
    # Season.DoesNotExist in the view, which gives a real 500 to test with.

    @classmethod
    def setUpTestData(cls):
        Season.objects.create(season_start_year=2025)
        cls.staff = User.objects.create_user("staff", password="p", is_staff=True)
        cls.member = User.objects.create_user("member", password="p")

    def setUp(self):
        self.client.raise_request_exception = False

    def upload_to_missing_season(self):
        return self.client.post(
            reverse("races:new"),
            {
                "name": "Linn Park",
                "season_start_year": 2030,
                "race_file": generate_file_with_runners(),
            },
        )

    def test_staff_see_the_error_and_traceback(self):
        self.client.force_login(self.staff)
        response = self.upload_to_missing_season()
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "DoesNotExist", status_code=500)
        self.assertContains(response, "Season matching query does not exist", status_code=500)
        self.assertContains(response, "Traceback", status_code=500)
        self.assertContains(response, "races/views.py", status_code=500)

    def test_non_staff_get_the_plain_error_page(self):
        self.client.force_login(self.member)
        response = self.upload_to_missing_season()
        self.assertEqual(response.status_code, 500)
        self.assertNotContains(response, "DoesNotExist", status_code=500)
        self.assertNotContains(response, "Traceback", status_code=500)
