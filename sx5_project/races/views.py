import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.shortcuts import get_list_or_404
import pandas as pd
from django.db import transaction
from typing import Any, Dict
from django.shortcuts import render
from django.urls import reverse_lazy
from pathlib import Path
from races.utils import create_result_versions


from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from races.models import Race, Result, Runner, RaceVersion

from races.forms import RaceForm


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

    @transaction.atomic
    def form_valid(self, form):
        race = form.save(commit=False)

        race_count = Race.objects.count()
        race_number = race_count + 1
        race.race_number = race_number

        race.save()

        self.object = race

        if self.request.FILES:
            excel_file = self.request.FILES['race_file']
            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            uploaded_file_url = fs.url(filename)

            uploaded_file_path = os.path.join(settings.MEDIA_ROOT, filename)

            df = pd.read_excel(uploaded_file_path)

            results = []
            for index, row in df.iterrows():
                first_name = row['First Name']
                middle_name = row['Middle Name']
                last_name = row['Last Name']
                category = row['Category']
                time = pd.to_timedelta(row['Time'])

                runner, created = Runner.objects.get_or_create(
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    category=category
                )

                result = Result(
                    race=self.object,
                    runner=runner,
                    time=time
                )
                results.append(result)

            # Save all results at once
            Result.objects.bulk_create(results)

            # Refresh results from db
            results = list(self.object.result_set.all())

            self.object.calculate_positions()
            create_result_versions(self.object)

        return super().form_valid(form)


class RaceUpdateView(UpdateView):
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
                first_name, middle_name, last_name, category, time = row
                runner, _ = Runner.objects.get_or_create(
                    first_name=first_name, middle_name=middle_name, last_name=last_name, category=category)
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


class RaceVersionListView(ListView):
    model = RaceVersion
    template_name = 'race_versions/race_version_list.html'
    context_object_name = 'race_versions'


class RaceVersionDetailView(DetailView):
    model = RaceVersion
    template_name = 'race_versions/race_version_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['result_versions'] = self.object.result_versions.all()
        return context
