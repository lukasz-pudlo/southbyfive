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

    # This ensures that all database operations in this block are executed as a single transaction
    @transaction.atomic
    def form_valid(self, form):
        self.object = form.save()
        if self.request.FILES:
            excel_file = self.request.FILES['race_file']
            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            uploaded_file_url = fs.url(filename)

            uploaded_file_path = os.path.join(settings.MEDIA_ROOT, filename)

            df = pd.read_excel(uploaded_file_path)

            for index, row in df.iterrows():
                # Here, 'First Name', 'Middle Name', 'Last Name', 'Category', and 'Time' are the column names in the Excel file.
                first_name = row['First Name']
                middle_name = row['Middle Name']
                last_name = row['Last Name']
                category = row['Category']
                # Convert time string to a pandas.Timedelta object.
                time = pd.to_timedelta(row['Time'])

                runner, created = Runner.objects.get_or_create(
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    category=category
                )

                Result.objects.create(
                    race=self.object,
                    runner=runner,
                    time=time
                )

        return super().form_valid(form)


class RaceUpdateView(UpdateView):
    model = Race
    template_name = 'races/race_form.html'
    fields = ['name', 'description', 'race_date', 'race_file']


class RaceDeleteView(DeleteView):
    model = Race
    template_name = 'races/race_confirm_delete.html'
    success_url = reverse_lazy('races:list')
