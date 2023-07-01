from django.contrib import admin

from races.models import Race, Runner, Result
from races.forms import ResultForm


class ResultAdmin(admin.ModelAdmin):
    form = ResultForm
    readonly_fields = ['time']


models = [Race, Runner]
admin_classes = {Result: ResultAdmin}

for model in models:
    admin.site.register(model)

for model, admin_class in admin_classes.items():
    admin.site.register(model, admin_class)
