"""The working shown when hovering over a runner in the Series standings."""

import pytest
from django.urls import reverse

from classifications.breakdown import standings_breakdown
from classifications.models import ClassificationResult
from races.models import Race, Runner
from sx5_project.tests.test_results_import import (  # noqa: F401
    plain_static_storage,
    publish,
    season,
    staff,
)

pytestmark = pytest.mark.django_db

# forename, surname, club, category, number, seconds
ANN = ("Ann", "Archer", "Club A", "FS", 1)
BOB = ("Bob", "Baker", "Club A", "MS", 2)
CAT = ("Cat", "Cooper", "", "F40", 3)
DAN = ("Dan", "Dixon", "Club B", "M40", 4)
EVE = ("Eve", "Ellis", "Club B", "FS", 5)
ZED = ("Zed", "Zimmer", "", "MS", 6)

PARKS = ["King's Park", "Linn Park", "Rouken Glen", "Pollok Park"]


def field(*runners):
    """Rows finishing in the order given, a minute apart."""
    return [runner + (1200.0 + 60 * i,) for i, runner in enumerate(runners)]


def runner(first_name):
    return Runner.objects.get(first_name=first_name)


def race(name):
    return Race.objects.get(name=name)


def points(breakdown, column):
    """One column of the breakdown, as (points, left out) per race run."""
    return [
        (row["cells"][column]["points"], row["cells"][column]["dropped"])
        for row in breakdown["rows"]
        if row["ran"]
    ]


@pytest.fixture
def four_races(season, staff):  # noqa: F811
    """Zed wins the first race and never comes back. Dan misses the third."""
    publish(season, staff, field(ZED, ANN, BOB, CAT, DAN, EVE), PARKS[0])
    publish(season, staff, field(ANN, BOB, CAT, DAN, EVE), PARKS[1])
    publish(season, staff, field(ANN, BOB, CAT, EVE), PARKS[2])
    publish(season, staff, field(ANN, BOB, CAT, DAN, EVE), PARKS[3])


def test_after_one_race_points_are_the_places(season, staff):  # noqa: F811
    publish(season, staff, field(ANN, BOB, CAT, DAN, EVE), PARKS[0])
    b = standings_breakdown(race(PARKS[0]), runner("Eve").id)
    assert b["reconciles"]
    assert b["total_races"] == 1
    assert not b["drops_worst"] and not b["reranked"]
    assert [points(b, column) for column in range(3)] == [
        [(5, False)],  # fifth overall
        [(3, False)],  # third woman
        [(2, False)],  # second FS
    ]
    assert b["totals"] == [5, 3, 2]


def test_the_worst_result_is_left_out_per_column(season, staff):  # noqa: F811
    # Cat is 2nd overall and 2nd woman, then 3rd overall and 1st woman.
    publish(season, staff, field(ANN, CAT, BOB, DAN, EVE), PARKS[0])
    publish(season, staff, field(BOB, DAN, CAT, ANN, EVE), PARKS[1])
    b = standings_breakdown(race(PARKS[1]), runner("Cat").id)
    assert b["reconciles"] and b["drops_worst"]
    assert points(b, 0) == [(2, False), (3, True)]
    assert points(b, 1) == [(2, True), (1, False)]
    assert b["totals"] == [2, 1, 1]


def test_points_are_places_among_the_runners_still_in(four_races):
    b = standings_breakdown(race(PARKS[3]), runner("Bob").id)
    assert b["reconciles"] and b["reranked"] and b["drops_worst"]
    assert b["runners_in_standings"] == 5
    assert b["races_needed"] == 3
    # Third behind Zed on the day, second once Zed is taken out.
    first = b["rows"][0]["cells"][0]
    assert (first["points"], first["place_on_the_day"]) == (2, "3rd")
    assert b["moved_up"]
    assert b["totals"] == [6, 3, 3]


def test_a_runner_who_missed_a_race_keeps_every_result(four_races):
    b = standings_breakdown(race(PARKS[3]), runner("Dan").id)
    assert b["reconciles"] and not b["drops_worst"]
    assert [missed.name for missed in b["missed"]] == [PARKS[2]]
    assert [row["ran"] for row in b["rows"]] == [True, True, False, True]
    assert points(b, 0) == [(4, False), (4, False), (4, False)]
    assert b["totals"] == [12, 6, 3]


def test_earlier_standings_keep_the_points_they_were_made_with(four_races):
    # After two races nobody had been taken out, so Zed still counted.
    b = standings_breakdown(race(PARKS[1]), runner("Bob").id)
    assert b["reconciles"] and not b["reranked"]
    assert b["total_races"] == 2
    assert points(b, 0) == [(3, True), (2, False)]
    assert b["rows"][0]["cells"][0]["place_on_the_day"] == ""


def test_every_row_of_every_standings_adds_up(four_races):
    checked = 0
    for row in ClassificationResult.objects.select_related("classification__race"):
        b = standings_breakdown(row.classification.race, row.runner_id)
        assert b["reconciles"], (row.classification.race.name, str(row.runner))
        checked += 1
    assert checked == 6 + 6 + 5 + 5


def test_a_runner_outside_the_standings_has_no_breakdown(four_races):
    assert standings_breakdown(race(PARKS[3]), runner("Zed").id) is None
    assert standings_breakdown(race(PARKS[0]), runner("Zed").id) is not None


def url(race_name, first_name):
    the_race = race(race_name)
    return reverse(
        "races:standings_explain",
        args=[the_race.season_start_year, the_race.slug, runner(first_name).id],
    )


def panel(client, race_name, first_name):
    """The panel's HTML with runs of whitespace collapsed."""
    response = client.get(url(race_name, first_name))
    assert response.status_code == 200
    return " ".join(response.content.decode().split())


def test_the_panel_shows_the_working(client, four_races):
    html = panel(client, PARKS[3], "Bob")
    assert "Bob Baker" in html
    assert "Series standings after Pollok Park, 4 races so far" in html
    assert "<small>3rd " in html and "on the day, counted as" in html
    assert "<s title=\"Left out\">2</s>" in html
    assert "among the 5" in html and "at least 3 of the" in html
    assert "has run all 4 races" in html


def test_the_panel_names_a_missed_race(client, four_races):
    html = panel(client, PARKS[3], "Dan")
    assert "did not run" in html
    assert "Dan Dixon did not run Rouken Glen" in html
    assert "all 3 results count" in html


def test_the_panel_is_missing_for_a_runner_not_in_the_standings(client, four_races):
    assert client.get(url(PARKS[3], "Zed")).status_code == 404
    missing_race = url(PARKS[3], "Bob").replace("pollok-park", "no-such-park")
    assert client.get(missing_race).status_code == 404


def test_working_that_does_not_add_up_is_not_shown(client, four_races):
    row = ClassificationResult.objects.get(
        classification__race=race(PARKS[3]), runner=runner("Bob")
    )
    row.general_points += 1
    row.save()
    html = panel(client, PARKS[3], "Bob")
    assert "<table" not in html
    assert "has 7 general, 3 gender and 3 category points" in html
    assert "can't be shown" in html


def test_each_standings_row_links_to_its_working(client, four_races):
    the_race = race(PARKS[3])
    page = client.get(the_race.get_absolute_url() + "?tab=classification-results")
    html = page.content.decode()
    assert page.status_code == 200
    assert html.count("data-explain-url=") == 5
    assert url(PARKS[3], "Bob") in html
