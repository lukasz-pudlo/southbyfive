from django.contrib import admin

from results_import.models import ImportRule, ResultsUpload


@admin.register(ResultsUpload)
class ResultsUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "race_name", "season", "status", "uploaded_at", "uploaded_by")
    list_filter = ("status", "season")
    exclude = ("original_file",)
    readonly_fields = ("sha256", "versions_before", "created_runner_ids")


@admin.register(ImportRule)
class ImportRuleAdmin(admin.ModelAdmin):
    list_display = ("kind", "from_label", "to_label", "active", "created_at")
    list_filter = ("kind", "active")
