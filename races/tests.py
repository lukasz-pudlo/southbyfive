from datetime import date, datetime, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import Race, Result, Runner, Season


class RaceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        season_object = Season.objects.create(
            season_start_year=2025
        )
        Race.objects.create(
            season=season_object,
            name="Test Race",
            description="Test Description",
            race_date=date.today(),
            season_start_year=2025
        )

    def test_name_label(self):
        race = Race.objects.get(id=1)
        field_label = race._meta.get_field("name").verbose_name
        self.assertEqual(field_label, "name")

    def test_description_label(self):
        race = Race.objects.get(id=1)
        field_label = race._meta.get_field("description").verbose_name
        self.assertEqual(field_label, "description")

    def test_race_date_label(self):
        race = Race.objects.get(id=1)
        field_label = race._meta.get_field("race_date").verbose_name
        self.assertEqual(field_label, "race date")

    def test_date_added_auto_now(self):
        race = Race.objects.get(id=1)
        auto_now = race._meta.get_field("date_added").auto_now
        self.assertTrue(auto_now)

    def test_date_modified_auto_now_add(self):
        race = Race.objects.get(id=1)
        auto_now_add = race._meta.get_field("date_modified").auto_now_add
        self.assertTrue(auto_now_add)

    def test_object_name_is_race_name(self):
        race = Race.objects.get(id=1)
        expected_object_name = f"{race.name}"
        self.assertEqual(expected_object_name, str(race))

    def test_get_absolute_url(self):
        race = Race.objects.get(id=1)
        # This will also fail if the urlconf is not defined.
        self.assertEqual(race.get_absolute_url(), f"/races/{race.id}/")

    def test_ordering(self):
        self.assertEqual(Race._meta.ordering, ["date_added"])


class RunnerModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Runner.objects.create(
            first_name="Test", last_name="Runner", category="M50"
        )

    def test_first_name_label(self):
        runner = Runner.objects.get(id=1)
        field_label = runner._meta.get_field("first_name").verbose_name
        self.assertEqual(field_label, "first name")

    def test_last_name_label(self):
        runner = Runner.objects.get(id=1)
        field_label = runner._meta.get_field("last_name").verbose_name
        self.assertEqual(field_label, "last name")

    def test_category_label(self):
        runner = Runner.objects.get(id=1)
        field_label = runner._meta.get_field("category").verbose_name
        self.assertEqual(field_label, "category")

    def test_first_name_max_length(self):
        runner = Runner.objects.get(id=1)
        max_length = runner._meta.get_field("first_name").max_length
        self.assertEqual(max_length, 255)

    def test_last_name_max_length(self):
        runner = Runner.objects.get(id=1)
        max_length = runner._meta.get_field("last_name").max_length
        self.assertEqual(max_length, 255)

    def test_category_choices(self):
        runner = Runner.objects.get(id=1)
        field_choices = runner._meta.get_field("category").choices
        self.assertEqual(field_choices, Runner.RUNNER_CATEGORIES)

    def test_str(self):
        runner = Runner.objects.get(id=1)
        expected_object_name = (
            f"{runner.first_name} {runner.last_name}"
        )
        self.assertEqual(expected_object_name, str(runner))

    def test_category_null(self):
        runner = Runner.objects.get(id=1)
        field_null = runner._meta.get_field("category").null
        self.assertEqual(field_null, True)


class ResultModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        season_object = Season.objects.create(
            season_start_year="2025"
        )
        race = Race.objects.create(
            season=season_object,
            name="Test Race",
            description="Test Race Description",
            race_date=date.today(),
            race_file=SimpleUploadedFile("test_file.txt", b"This is a test file"),
        )
        runner = Runner.objects.create(
            first_name="Test", last_name="Runner", category="M50"
        )
        Result.objects.create(
            race=race, runner=runner, time=timedelta(hours=1, minutes=30, seconds=15)
        )

    def test_time_label(self):
        result = Result.objects.get(id=1)
        field_label = result._meta.get_field("time").verbose_name
        self.assertEqual(field_label, "time")
