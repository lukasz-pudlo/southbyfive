from django.shortcuts import render
from race_versions.models import RaceVersion
from django.views.generic import ListView, DetailView


class RaceVersionListView(ListView):
    model = RaceVersion
    template_name = 'race_versions/race_version_list.html'
    context_object_name = 'race_versions'


class RaceVersionDetailView(DetailView):
    model = RaceVersion
    template_name = 'race_versions/race_version_detail.html'
    context_object_name = 'race_version'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['result_versions'] = self.object.race_versions_result_versions.all()

        return context
