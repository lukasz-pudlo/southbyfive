"""Turning result rows into Runner and Result records.

Shared by the original "Add race" form and the results import, so both
produce the same runners, times and positions.
"""

import pandas as pd
from django.db import IntegrityError, transaction

from races.models import Result, Runner

DNF_TIME = "02:00:00"
UNAFFILIATED = "Unaffiliated"


def get_or_create_runner(
    first_name, last_name, participant_number, category, club, season
):
    try:
        with transaction.atomic():
            # Try to get or create the runner
            runner, created = Runner.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
                season=season,
                defaults={
                    "participant_number": participant_number,
                    "category": category,
                    "club": club,
                    "season": season,
                },
            )
    except IntegrityError:
        # Handle race condition where another process creates the runner
        runner = Runner.objects.get(
            first_name=first_name,
            last_name=last_name,
        )
        # Optionally update details if needed
        runner.participant_number = participant_number
        runner.category = category
        runner.club = club
        runner.save()
        created = False
    return runner, created


def parse_result_time(time_str):
    """A finish time as stored on a Result.

    "DNF" is stored as two hours, as it always has been. A tie-break number
    after the time ("00:19:20 1", "00:19:20 2") is added as microseconds, so
    the times look the same but keep their order.
    """
    if time_str == "DNF":
        return pd.to_timedelta(DNF_TIME)

    time_parts = str(time_str).split()
    time = pd.to_timedelta(time_parts[0])
    if len(time_parts) > 1:
        try:
            time += pd.Timedelta(microseconds=int(time_parts[1]))
        except ValueError:
            pass  # If not a valid number, just use base time
    return time


def create_results_for_race(race, season, rows):
    """Create the race's results from ``rows``: dicts with first_name,
    last_name, participant_number, category, club and time.

    Returns ``(results, created_runners)``. A runner who already has a record
    this season keeps that record's number, category and club.
    """
    results = []
    created_runners = []
    for row in rows:
        club = row["club"]
        if club is None or pd.isnull(club) or club == "":
            club = UNAFFILIATED
        runner, created = get_or_create_runner(
            first_name=row["first_name"],
            last_name=row["last_name"],
            participant_number=row["participant_number"],
            category=row["category"],
            club=club,
            season=season,
        )
        if created:
            created_runners.append(runner)
        results.append(
            Result(
                race=race,
                runner=runner,
                time=parse_result_time(row["time"]),
                dnf=False,
            )
        )

    Result.objects.bulk_create(results)
    return results, created_runners
