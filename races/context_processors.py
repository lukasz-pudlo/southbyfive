from .models import Race
from datetime import date


def race_list(request):
    races = Race.objects.all().order_by('date_added')
    return {'races': races}


def race_navbar(request):
    # Determine the selected season, defaulting to the most recent season if none is provided
    season = request.GET.get(
        'season') or request.session.get('selected_season')

    if season is None:
        # Default to the most recent season
        season = Race.objects.order_by(
            '-season_start_year').values_list('season_start_year', flat=True).first()

    # Save the selected season in session to maintain it across requests
    request.session['selected_season'] = season

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

    return {'race_navbar': races, 'selected_season': int(season)}


def race_dates_context(request):
    race_dates = {
        "King's Park": date(2023, 11, 5),
        'Linn Park': date(2023, 11, 19),
        'Rouken Glen': date(2023, 12, 3),
        'Pollok Park': date(2023, 12, 17),
        'Bellahouston Park': date(2024, 1, 7),
        "Queen's Park": date(2024, 1, 21),
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
    selected_season = request.session.get('selected_season')
    if not selected_season:
        # Default to the most recent season if no season is selected
        selected_season = Race.objects.order_by(
            '-season_start_year').values_list('season_start_year', flat=True).first()
        request.session['selected_season'] = selected_season

    park_names = [
        "King's Park",
        "Linn Park",
        "Rouken Glen",
        "Pollok Park",
        "Bellahouston Park",
        "Queen's Park"
    ]

    # Get the latest race for each park in the selected season
    races = {
        name: Race.objects.filter(
            name=name, season_start_year=selected_season).order_by('-race_date').first()
        for name in park_names
    }

    # Prepare the dictionary for the navbar, associating each park with its latest race in the selected season
    race_navbar_with_dates = {name: {'race': race}
                              for name, race in races.items()}

    return {
        'race_navbar_with_dates': race_navbar_with_dates,
        'selected_season': int(selected_season),
    }


def available_seasons(request):
    seasons = Race.objects.values_list(
        'season_start_year', flat=True).distinct().order_by('season_start_year')
    return {'seasons': seasons}
