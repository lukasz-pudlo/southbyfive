from django.test import TestCase, override_settings
from django.urls import reverse

from races.models import Race, Season


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
class TestRaceDetailView(TestCase):
    # Unknown pages are redirected home by the custom 404 handler
    # (races.views.custom_404), so a missing race should land there, not 500.

    @classmethod
    def setUpTestData(cls):
        season = Season.objects.create(season_start_year=2025)
        cls.race = Race.objects.create(
            name="Kings Park", season_start_year=2025, season=season, race_number=1
        )

    def test_existing_race_returns_200(self):
        url = reverse("races:detail", kwargs={"year": 2025, "slug": self.race.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_unknown_slug_redirects_home(self):
        url = reverse("races:detail", kwargs={"year": 2025, "slug": "no-such-race"})
        response = self.client.get(url)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_race_from_another_season_redirects_home(self):
        url = reverse("races:detail", kwargs={"year": 2024, "slug": self.race.slug})
        response = self.client.get(url)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_unknown_race_does_not_change_selected_season(self):
        url = reverse("races:detail", kwargs={"year": 2019, "slug": "no-such-race"})
        self.client.get(url)
        self.assertNotIn("selected_season", self.client.session)
