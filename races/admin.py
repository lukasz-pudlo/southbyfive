from django.contrib import admin

from race_versions.models import RaceVersion, ResultVersion
from races.forms import RaceForm, ResultForm
from races.models import Race, Result, Runner, Season


class SeasonAdmin(admin.ModelAdmin):
    pass


class ResultAdmin(admin.ModelAdmin):
    form = ResultForm
    readonly_fields = ["time"]
    list_display = (
        "id",
        "race",
        "runner",
        "time",
        "general_position",
        "gender_position",
        "category_position",
    )


class RaceAdmin(admin.ModelAdmin):
    form = RaceForm
    list_display = ("id", "name", "race_date",
                    "race_number", "season_start_year")


class RunnerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "participant_number",
        "club",
        "category",
    )
    search_fields = (
        "first_name",
        "last_name",
        "participant_number",
        "club",
        "category",
    )


class ResultVersionAdmin(admin.ModelAdmin):

    # Define methods to fetch attributes from the related Result instance

    def race(self, obj):
        return obj.result.race.name

    def runner(self, obj):
        return obj.result.runner

    def time(self, obj):
        return obj.result.time

    def general_position(self, obj):
        return obj.result.general_position

    def gender_position(self, obj):
        return obj.result.gender_position

    def category_position(self, obj):
        return obj.result.category_position

    # Adjust the list_display and readonly_fields attributes
    list_display = (
        "version",
        "race",
        "runner",
        "time",
        "general_points",
        "gender_points",
        "category_points",
    )

    readonly_fields = (
        "race",
        "runner",
        "time",
        "general_position",
        "gender_position",
        "category_position",
    )


class RaceVersionAdmin(admin.ModelAdmin):

    def name(self, obj):
        return obj.race.name

    def race_date(self, obj):
        return obj.race.race_date

    def race_number(self, obj):
        return obj.race.race_number

    list_display = ("id", "name", "race_date", "race_number")


models = [Race, Runner, Result, ResultVersion, Season]
admin_classes = {
    Race: RaceAdmin,
    Runner: RunnerAdmin,
    Result: ResultAdmin,
    ResultVersion: ResultVersionAdmin,
    RaceVersion: RaceVersionAdmin,
    Season: SeasonAdmin,
}

for model, admin_class in admin_classes.items():
    admin.site.register(model, admin_class)
