from django.db.models import Prefetch
from django.shortcuts import render
from django.views.generic import DetailView, ListView

from race_versions.models import RaceVersion, ResultVersion


class RaceVersionListView(ListView):
    model = RaceVersion
    template_name = "race_versions/race_version_list.html"
    context_object_name = "race_versions"


class RaceVersionDetailView(DetailView):
    model = RaceVersion
    template_name = "race_versions/race_version_detail.html"
    context_object_name = "race_version"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        race_version = self.object
        result_versions_prefetch = Prefetch(
            "race_versions_result_versions",
            queryset=ResultVersion.objects.all().select_related("related_model_if_any"),
        )
        context["result_versions"] = (
            RaceVersion.objects.prefetch_related(result_versions_prefetch)
            .get(id=race_version.id)
            .race_versions_result_versions.all()
        )
        return context
