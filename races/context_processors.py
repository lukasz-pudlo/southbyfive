from .models import Race
from datetime import date


def race_list(request):
    races = Race.objects.all().order_by('date_added')
    return {'races': races}


def race_navbar(request):

    park_names = [
        "King's Park",
        "Linn Park",
        "Rouken Glen",
        "Pollok Park",
        "Bellahouston Park",
        "Queen's Park"
    ]

    # Try to get each race, or set it to None if not found.
    races = {name: Race.objects.filter(name=name).first()
             for name in park_names}

    return {'race_navbar': races}


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
