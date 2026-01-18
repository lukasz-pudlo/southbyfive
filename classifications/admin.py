from django.contrib import admin

from classifications.models import Classification, ClassificationResult


class ClassificationAdmin(admin.ModelAdmin):

    # Define methods to fetch attributes from the related Race instance
    def classification_name(self, obj):
        return f"Classification after {obj.race.name}"

    # Adjust the list_display and other attributes
    list_display = ("id", "classification_name", "version_number")
    readonly_fields = ("classification_name",)
    ordering = ["race", "version_number"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("race")


class ClassificationResultAdmin(admin.ModelAdmin):

    # Define methods to fetch attributes from the related Runner and Classification instances
    def runner_name(self, obj):
        return obj.runner.first_name + " " + obj.runner.last_name

    def classification_version(self, obj):
        return f"Classification after {obj.classification.race.name}"

    def classification_id(self, obj):
        return obj.classification.id

    def classification_slug(self, obj):
        return obj.classification.slug

    # Adjust the list_display and other attributes
    list_display = (
        "id",
        "classification_slug",
        "runner_name",
        "classification_id",
        "classification_version",
        "general_points",
        "gender_points",
        "category_points",
    )
    readonly_fields = (
        "runner_name", "classification_version", "classification_id")
    ordering = ["-general_points"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("runner", "classification", "classification__race")
        )


models = [Classification, ClassificationResult]
admin_classes = {
    Classification: ClassificationAdmin,
    ClassificationResult: ClassificationResultAdmin,
}

for model, admin_class in admin_classes.items():
    admin.site.register(model, admin_class)
