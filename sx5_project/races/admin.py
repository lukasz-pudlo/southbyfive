from django.contrib import admin

from races.models import Race, Runner, Result
from races.forms import ResultForm, RaceForm


class ResultAdmin(admin.ModelAdmin):
    form = ResultForm
    readonly_fields = ['time']
    list_display = ('id', 'race', 'runner', 'time',
                    'general_position', 'gender_position', 'category_position')


class RaceAdmin(admin.ModelAdmin):
    form = RaceForm
    list_display = ('id', 'name', 'race_date', 'race_number')


class RunnerAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'middle_name', 'last_name', 'category')


models = [Race, Runner, Result]
admin_classes = {Race: RaceAdmin, Runner: RunnerAdmin, Result: ResultAdmin}

for model, admin_class in admin_classes.items():
    admin.site.register(model, admin_class)
