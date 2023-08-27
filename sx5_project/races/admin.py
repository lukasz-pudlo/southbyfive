from django.contrib import admin

from races.models import Race, Runner, Result, Classification, ClassificationResult
from race_versions.models import ResultVersion, RaceVersion
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
    list_display = ('version', 'race', 'runner', 'time',
                    'general_points', 'gender_points', 'category_points')

    readonly_fields = ('race', 'runner', 'time', 'general_position',
                       'gender_position', 'category_position')


class RaceVersionAdmin(admin.ModelAdmin):

    def name(self, obj):
        return obj.race.name

    def race_date(self, obj):
        return obj.race.race_date

    def race_number(self, obj):
        return obj.race.race_number

    list_display = ('id', 'name', 'race_date',
                    'race_number')


class ClassificationAdmin(admin.ModelAdmin):

    # Define methods to fetch attributes from the related Race instance
    def race_name(self, obj):
        return obj.race.name

    # Adjust the list_display and other attributes
    list_display = ('id', 'race_name', 'version_number')
    readonly_fields = ('race_name', )
    ordering = ['race', 'version_number']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('race')


class ClassificationResultAdmin(admin.ModelAdmin):

    # Define methods to fetch attributes from the related Runner and Classification instances
    def runner_name(self, obj):
        return obj.runner.first_name + " " + obj.runner.last_name

    def classification_version(self, obj):
        return f"Version {obj.classification.version_number} of {obj.classification.race.name}"

    # Adjust the list_display and other attributes
    list_display = ('id', 'runner_name', 'classification_version',
                    'general_points', 'gender_points', 'category_points')
    readonly_fields = ('runner_name', 'classification_version')
    ordering = ['-general_points']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('runner', 'classification', 'classification__race')


models = [Race, Runner, Result, ResultVersion]
admin_classes = {Race: RaceAdmin, Runner: RunnerAdmin,
                 Result: ResultAdmin, ResultVersion: ResultVersionAdmin, RaceVersion: RaceVersionAdmin, Classification: ClassificationAdmin,
                 ClassificationResult: ClassificationResultAdmin}

for model, admin_class in admin_classes.items():
    admin.site.register(model, admin_class)
