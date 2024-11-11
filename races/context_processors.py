from .models import Race
from datetime import date

# Define a dictionary of scheduled dates for each park
RACE_SCHEDULE_DATES = {
    "King's Park": date(2023, 11, 5),
    'Linn Park': date(2023, 11, 19),
    'Rouken Glen': date(2023, 12, 3),
    'Pollok Park': date(2023, 12, 17),
    'Bellahouston Park': date(2024, 1, 7),
    "Queen's Park": date(2024, 1, 21),
}


def race_list(request):
    races = Race.objects.all().order_by('date_added')
    return {'races': races}


def race_navbar(request):
    # Determine the selected season, defaulting to the most recent season if none is provided
    season = request.GET.get(
        'season') or request.session.get('selected_season')

    if season is None:
        # Default to the most recent season if `season` is still None
        season = Race.objects.order_by(
            '-season_start_year').values_list('season_start_year', flat=True).first()

    # Save the selected season in session to maintain it across requests
    request.session['selected_season'] = season

    # Ensure `season` is an integer if it's not None, otherwise use a default
    season = int(season) if season is not None else date.today().year

    # Filter races by the selected season and order by the specified parks
    park_names = [
        "King's Park",
        "Linn Park",
        "Rouken Glen",
        "Pollok Park",
        "Bellahouston Park",
        "Queen's Park"
    ]

    # Retrieve the latest race for each park within the selected season
    races = {name: Race.objects.filter(name=name, season_start_year=season).order_by('-race_date').first()
             for name in park_names}

    return {'race_navbar': races, 'selected_season': season}


def race_dates_context(request):
    race_dates = {
        "King's Park": date(2024, 11, 3),
        'Linn Park': date(2024, 11, 17),
        'Rouken Glen': date(2024, 12, 1),
        'Pollok Park': date(2023, 12, 15),
        'Bellahouston Park': date(2025, 1, 5),
        "Queen's Park": date(2025, 1, 19),
    }

    race_navbar_with_dates = {}
    for race_name, race_date in race_dates.items():
        race = Race.objects.filter(name=race_name).first()
        race_navbar_with_dates[race_name] = {
            'race': race,
            'date': race_date,
            'has_passed': date.today() > race_date
        }

    return {'race_navbar_with_dates': race_navbar_with_dates}


def race_navbar_with_dates(request):
    # Determine the selected season
    season = request.GET.get(
        'season') or request.session.get('selected_season')
    if season is None:
        season = Race.objects.order_by(
            '-season_start_year').values_list('season_start_year', flat=True).first()
        if season is None:
            season = date.today().year

    season = int(season)

    park_names = [
        "King's Park",
        "Linn Park",
        "Rouken Glen",
        "Pollok Park",
        "Bellahouston Park",
        "Queen's Park"
    ]

    races = {}
    for name in park_names:
        race = Race.objects.filter(
            name=name, season_start_year=season).order_by('-race_date').first()

        if race:
            # Race is available for this season
            races[name] = {
                'race': race,
                'available': True,
                'race_date': race.race_date
            }
        else:
            # Use scheduled date from RACE_SCHEDULE_DATES if race is not yet available
            scheduled_race_date = RACE_SCHEDULE_DATES.get(name)
            races[name] = {
                'race': None,
                'available': False,
                'race_date': scheduled_race_date  # Date from predefined schedule
            }

    return {'race_navbar': races, 'selected_season': season}


def available_seasons(request):
    seasons = Race.objects.values_list(
        'season_start_year', flat=True).distinct().order_by('season_start_year')
    return {'seasons': seasons}
