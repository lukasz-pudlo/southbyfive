from typing import Any, Dict
from django.shortcuts import render
from django.urls import reverse_lazy

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from races.models import Race, Result, Runner

from .forms import RaceForm


class RaceListView(ListView):
    model = Race
    template_name = 'races/race_list.html'
    context_object_name = 'races'


class RaceDetailView(DetailView):
    model = Race
    template_name = 'races/race_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['results'] = self.object.result_set.all()
        return context


class RaceCreateView(CreateView):
    model = Race
    template_name = 'races/race_form.html'
    form_class = RaceForm


class RaceUpdateView(UpdateView):
    model = Race
    template_name = 'races/race_form.html'
    fields = ['name', 'description', 'race_date', 'race_file']


class RaceDeleteView(DeleteView):
    model = Race
    template_name = 'races/race_confirm_delete.html'
    success_url = reverse_lazy('races:list')
