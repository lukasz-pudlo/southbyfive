import pytest

from races.models import Runner, Season


@pytest.fixture
def runner_callum(db):
    season = Season.objects.create(season_start_year=2025)
    runner = Runner.objects.create(
        first_name="Callum",
        last_name="Wallace",
        participant_number="123",
        category="MS",
        club="Bellahouston Harriers",
        season=season
    )

    return runner


def test_should_create_runner(runner_callum):
    assert runner_callum.first_name == "Callum"
