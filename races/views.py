import os
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile

import pandas as pd
from pandas import isnull
from django.db import transaction
from typing import Any, Dict
from django.urls import reverse_lazy
from pathlib import Path
from races.utils import create_result_versions
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from races.models import Race, Result, Runner

from races.forms import RaceForm
from classifications.models import ClassificationResult


def home(request):
    first_race = Race.objects.last()
    if first_race is not None:
        return redirect('races:detail', first_race.id)
    else:
        return redirect('races:list')


class RaceListView(ListView):
    model = Race
    template_name = 'races/race_list.html'
    context_object_name = 'races'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['races'] = Race.objects.all()
        return context


class RaceDetailView(DetailView):
    model = Race
    template_name = 'races/race_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        race = self.object
        context['results'] = race.result_set.select_related('runner').all()
        context['classification_results'] = ClassificationResult.objects.filter(
            classification__race=race
        ).select_related('runner', 'classification')

        context['active_park_name'] = race.name
        context['active_tab'] = self.request.GET.get('tab', 'race-results')

        return context


class RaceCreateView(LoginRequiredMixin, CreateView):
    model = Race
    template_name = 'races/race_form.html'
    form_class = RaceForm

    @transaction.atomic
    def form_valid(self, form):
        print("Debug: form_valid in RaceCreateView is being called.")
        race = form.save(commit=False)

        race_count = Race.objects.count()
        race_number = race_count + 1
        race.race_number = race_number

        race.save()

        print(f"Debug: Race object ID after save: {race.id}")

        self.object = race
        print(f"Debug: self.object ID after assignment: {self.object.id}")

        if self.request.FILES:
            excel_file = self.request.FILES['race_file']
            if isinstance(excel_file, InMemoryUploadedFile):
                df = pd.read_excel(excel_file)

                results = []
                for index, row in df.iterrows():
                    first_name = row['First Name']
                    last_name = row['Last Name']
                    participant_number = row['Participant Number']
                    category = row['Category']
                    club = row['Club'] if not isnull(
                        row['Club']) else 'Unattached'
                    time = pd.to_timedelta(row['Time'])

                    runner, created = Runner.objects.get_or_create(
                        first_name=first_name,
                        last_name=last_name,
                        participant_number=participant_number,
                        category=category,
                        club=club
                    )

                    result = Result(
                        race=self.object,
                        runner=runner,
                        time=time
                    )
                    results.append(result)

            # Save all results at once
            Result.objects.bulk_create(results)
            print(f"Debug: Number of results saved: {len(results)}")

            # Refresh results from db
            results = list(self.object.result_set.all())

            self.object.calculate_positions()

            # Now that all Result objects have been saved, call create_result_versions
            print(
                f"Debug: Race object ID before create_result_versions: {self.object.id}")

            create_result_versions(self.object)

        return super().form_valid(form)


class RaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Race
    template_name = 'races/race_form.html'
    fields = ['name', 'description', 'race_date', 'race_file']

    def form_valid(self, form):
        # If race_file has changed, delete old results and create new ones
        if 'race_file' in form.changed_data:
            self.object = form.save()

            # Remove old results related to this race
            Result.objects.filter(race=self.object).delete()

            # Get the new data from the file
            data = pd.read_excel(self.object.race_file.path)
            for i, row in data.iterrows():
                first_name, last_name, category, club, time = row
                runner, _ = Runner.objects.get_or_create(
                    first_name=first_name, last_name=last_name, category=category, club=club)
                Result.objects.get_or_create(
                    race=self.object, runner=runner, time=pd.to_timedelta(time))

            self.object.calculate_positions()

            return super().form_valid(form)
        else:
            return super().form_valid(form)


class RaceDeleteView(DeleteView):
    model = Race
    template_name = 'races/race_confirm_delete.html'
    success_url = reverse_lazy('races:list')


def custom_404(request, exception):
    return redirect('home')
