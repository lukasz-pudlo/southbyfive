from .models import Race


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
