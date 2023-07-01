from django.contrib import admin

from races.models import Race, Result, Runner

models = [Race, Result, Runner]

for model in models:
    admin.site.register(model)
