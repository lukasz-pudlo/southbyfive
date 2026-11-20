"""Planned race dates: entering them, and what the navigation shows."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from races.models import Race, ScheduledRace, Season

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def plain_static_storage(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }


@pytest.fixture
def season():
    season = Season.objects.create(season_start_year=2026)
    Race.objects.create(
        name="King's Park", season_start_year=2026, season=season, race_number=1
    )
    return season


@pytest.fixture
def staff_client(client):
    client.force_login(User.objects.create_user("owner", password="p", is_staff=True))
    return client


def nav(client):
    html = client.get(reverse("info:contact")).content.decode()
    return html[html.index("site-nav__parks") : html.index("site-nav__right")]


def test_a_race_with_no_planned_date_shows_no_date(client, season):
    html = nav(client)
    assert "Linn Park" in html
    assert "race-tooltip" not in html
    assert "2023" not in html
    assert "take place" not in html


def test_an_upcoming_race_shows_its_planned_date(client, season):
    soon = date.today() + timedelta(days=10)
    ScheduledRace.objects.create(season=season, name="Linn Park", race_date=soon)
    html = nav(client)
    assert html.count("race-tooltip") == 1
    assert f"This race will take place on {soon.day} {soon:%b %Y}" in html


def test_a_planned_date_that_has_passed_does_not_say_will(client, season):
    past = date.today() - timedelta(days=2)
    ScheduledRace.objects.create(season=season, name="Linn Park", race_date=past)
    html = nav(client)
    assert "will take place" not in html
    assert f"This race took place on {past.day} {past:%b %Y}" in html


def test_dates_belong_to_their_own_season(client, season):
    other = Season.objects.create(season_start_year=2025)
    ScheduledRace.objects.create(
        season=other, name="Linn Park", race_date=date.today() + timedelta(days=10)
    )
    assert "race-tooltip" not in nav(client)


def test_a_race_with_results_links_to_them_whatever_is_planned(client, season):
    ScheduledRace.objects.create(
        season=season, name="King's Park", race_date=date.today() + timedelta(days=3)
    )
    html = nav(client)
    assert "race-tooltip" not in html
    assert "kings-park-2026" in html


def test_only_staff_can_enter_dates(client, season):
    url = reverse("races:dates")
    assert client.get(url).status_code == 302
    client.force_login(User.objects.create_user("member", password="p"))
    assert client.get(url).status_code == 403
    assert client.post(url, {"park_1": "2026-11-15"}).status_code == 403
    assert ScheduledRace.objects.count() == 0


def test_dates_can_be_entered_changed_and_cleared(staff_client, season):
    url = reverse("races:season_dates", args=[2026])
    page = staff_client.get(reverse("races:dates"))
    assert page.status_code == 200
    assert "Race dates 2026/2027" in page.content.decode()

    staff_client.post(url, {"park_1": "2026-11-15", "park_2": "2026-11-29"})
    assert list(
        ScheduledRace.objects.order_by("race_date").values_list("name", "race_date")
    ) == [("Linn Park", date(2026, 11, 15)), ("Rouken Glen", date(2026, 11, 29))]
    assert 'value="2026-11-15"' in staff_client.get(url).content.decode()

    staff_client.post(url, {"park_1": "2026-11-16", "park_2": ""})
    assert list(ScheduledRace.objects.values_list("name", "race_date")) == [
        ("Linn Park", date(2026, 11, 16))
    ]


def test_an_upload_without_a_date_takes_the_planned_one(staff_client, season):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from results_import.models import ResultsUpload
    from sx5_project.tests.test_normalise import raw_file

    ScheduledRace.objects.create(
        season=season, name="Linn Park", race_date=date(2026, 11, 15)
    )
    staff_client.post(
        reverse("results_import:new"),
        {
            "results_file": SimpleUploadedFile(
                "Lx5.xlsx", raw_file([("Ann", "Archer", "", "FS", 1, 1200.0)])
            ),
            "race_name": "Linn Park",
            "season": season.pk,
        },
    )
    assert ResultsUpload.objects.get().race_date == date(2026, 11, 15)
