from .models import Race

def race_list(request):
    races = Race.objects.all().order_by('date_added')
    return {'races': races}
