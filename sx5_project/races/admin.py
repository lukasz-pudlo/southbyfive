from django.contrib import admin

from races.models import Race, Results, Runner

models = [Race, Results, Runner]

for model in models:
    admin.site.register(model)
