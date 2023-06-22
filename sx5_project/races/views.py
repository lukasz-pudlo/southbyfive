from django.shortcuts import render
from django.urls import reverse_lazy

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from races.models import Race

from .forms import RaceForm


class RaceListView(ListView):
    model = Race
    template_name = 'races/race_list.html'
    context_object_name = 'races'


class RaceDetailView(DetailView):
    model = Race
    template_name = 'races/race_detail.html'


class RaceCreateView(CreateView):
    model = Race
    template_name = 'races/race_form.html'
    form_class = RaceForm


class RaceUpdateView(UpdateView):
    model = Race
    template_name = 'races/race_form.html'
    fields = ['name', 'description', 'race_date']


class RaceDeleteView(DeleteView):
    model = Race
    template_name = 'races/race_confirm_delete.html'
    success_url = reverse_lazy('races:list')
