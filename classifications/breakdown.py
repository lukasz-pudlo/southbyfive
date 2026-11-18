"""Why a runner has the points shown in a race's Series standings.

Only the three totals are stored on ClassificationResult. This rebuilds the
race-by-race working behind them, following create_classification_entries in
races/utils.py, and checks it against the stored totals.
"""

import pandas as pd
from django.db.models import Min

from classifications.models import ClassificationResult
from race_versions.models import RaceVersion, ResultVersion
from races.importing import DNF_TIME
from races.models import Race
from races.utils import get_gender_from_category

COLUMNS = ("general", "gender", "category")
DNF = pd.to_timedelta(DNF_TIME).to_pytimedelta()


def ordinal(number):
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def versions_used(race, races):
    """The RaceVersion of each race that fed ``race``'s standings.

    Nothing records this, but every upload creates its versions before the
    next race exists. So the versions in use were the newest ones older than
    the first version of any race added later.
    """
    boundary = RaceVersion.objects.filter(
        race__season_start_year=race.season_start_year,
        race__date_added__gt=race.date_added,
    ).aggregate(Min("id"))["id__min"]
    versions = RaceVersion.objects.filter(race__in=races)
    if boundary is not None:
        versions = versions.filter(id__lt=boundary)
    return {
        version.race_id: version for version in versions.order_by("version_number")
    }


def standings_breakdown(race, runner_id):
    """The working behind one runner's row in ``race``'s standings.

    Returns None when the runner isn't in those standings. ``reconciles`` is
    False when the rebuilt totals differ from the stored ones, in which case
    the race-by-race figures should not be shown.
    """
    stored = (
        ClassificationResult.objects.filter(
            classification__race=race, runner_id=runner_id
        )
        .select_related("runner", "classification")
        .order_by("-classification__version_number")
        .first()
    )
    if stored is None:
        return None
    runner = stored.runner

    races = list(
        Race.objects.filter(
            season_start_year=race.season_start_year,
            date_added__lte=race.date_added,
        ).order_by("date_added", "id")
    )
    total_races = len(races)

    scored = {
        result_version.result.race_id: result_version
        for result_version in ResultVersion.objects.filter(
            result__runner=runner,
            race_version__in=versions_used(race, races).values(),
        ).select_related("result")
    }

    # The worst result goes only for a runner who has run every race so far,
    # and it is picked separately for each kind of points.
    drops_worst = total_races > 1 and len(scored) == total_races
    dropped = {}
    if drops_worst:
        for column in COLUMNS:
            dropped[column] = max(
                (r for r in races if r.id in scored),
                key=lambda r: (
                    getattr(scored[r.id], f"{column}_points") or 0,
                    r.date_added,
                    r.id,
                ),
            ).id

    rows = []
    totals = dict.fromkeys(COLUMNS, 0)
    for season_race in races:
        result_version = scored.get(season_race.id)
        if result_version is None:
            rows.append({"race": season_race, "ran": False})
            continue
        result = result_version.result
        cells = []
        for column in COLUMNS:
            points = getattr(result_version, f"{column}_points") or 0
            position = getattr(result, f"{column}_position")
            is_dropped = dropped.get(column) == season_race.id
            if not is_dropped:
                totals[column] += points
            cells.append(
                {
                    "points": points,
                    "dropped": is_dropped,
                    # The place on the day, when leaving out runners with
                    # too few races has moved this runner up.
                    "place_on_the_day": (
                        ordinal(position) if position and position != points else ""
                    ),
                }
            )
        rows.append(
            {
                "race": season_race,
                "ran": True,
                "dnf": result.time == DNF,
                "cells": cells,
            }
        )

    stored_totals = {
        column: getattr(stored, f"{column}_points") or 0 for column in COLUMNS
    }
    ran_rows = [row for row in rows if row["ran"]]
    return {
        "runner": runner,
        "race": race,
        "gender": get_gender_from_category(runner.category),
        "rows": rows,
        "totals": [stored_totals[column] for column in COLUMNS],
        "reconciles": totals == stored_totals,
        "total_races": total_races,
        "races_run": len(ran_rows),
        "races_needed": total_races - 1,
        "missed": [row["race"] for row in rows if not row["ran"]],
        "drops_worst": drops_worst,
        # From the third race on, each race is re-ranked among the runners
        # who are still in the standings.
        "reranked": total_races > 2,
        "runners_in_standings": ClassificationResult.objects.filter(
            classification=stored.classification
        ).count(),
        "has_dnf": any(row["dnf"] for row in ran_rows),
        "moved_up": any(
            cell["place_on_the_day"] for row in ran_rows for cell in row["cells"]
        ),
    }
