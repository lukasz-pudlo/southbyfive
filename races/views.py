import pandas as pd
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)
from pandas import isnull

from classifications.models import ClassificationResult
from races.forms import RaceForm
from races.models import Race, Result, Runner, Season
from races.utils import create_result_versions


def home(request):
    last_race = Race.objects.first()
    # Retrieve distinct season years for the Seasons dropdown
    seasons = (
        Race.objects.values_list("season_start_year", flat=True)
        .distinct()
        .order_by("season_start_year")
    )

    if last_race and last_race.season_start_year and last_race.slug:
        # Redirect to the detail view with both `year` and `slug` for the last race
        return redirect(
            "races:detail", year=last_race.season_start_year, slug=last_race.slug
        )
    else:
        # Fallback to the race list if no valid race is available
        return redirect("races:list")


class RaceListView(ListView):
    model = Race
    template_name = "races/race_list.html"
    context_object_name = "races"

    def get(self, request, *args, **kwargs):
        season = self.kwargs.get("season")

        if season:
            # Set the selected season in the session
            request.session["selected_season"] = season

            # Get the most recent race in the specified season
            recent_race = (
                Race.objects.filter(season_start_year=season)
                .order_by("-race_date")
                .first()
            )

            if recent_race:
                # Redirect to the most recent race's detail page
                return redirect(
                    "races:detail",
                    year=recent_race.season_start_year,
                    slug=recent_race.slug,
                )

        # If no season or race is found, display the full race list
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        season = self.kwargs.get("season") or self.request.session.get(
            "selected_season"
        )
        if season:
            queryset = queryset.filter(season_start_year=season)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add selected season to the context
        context["selected_season"] = self.kwargs.get(
            "season"
        ) or self.request.session.get("selected_season")
        return context


class RaceDetailView(DetailView):
    model = Race
    template_name = "races/race_detail.html"
    slug_field = "slug"

    def get_object(self, queryset=None):
        season_year = self.kwargs.get("year")
        slug = self.kwargs.get("slug")

        race = Race.objects.get(slug=slug, season_start_year=season_year)

        self.request.session["selected_season"] = season_year
        return race

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["selected_season"] = int(self.kwargs.get("year"))

        race = self.object
        context["results"] = race.result_set.select_related("runner").order_by(
            "general_position", "gender_position", "category_position"
        )

        context["classification_results"] = ClassificationResult.objects.filter(
            classification__race=race
        ).select_related("runner", "classification")

        context["active_park_name"] = race.name
        context["active_tab"] = self.request.GET.get("tab", "race-results")

        return context


# Ensure all runners are created or fetched without issues


def get_or_create_runner(
    first_name, last_name, participant_number, category, club, season
):
    try:
        with transaction.atomic():
            # Try to get or create the runner
            runner, created = Runner.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
                defaults={
                    "participant_number": participant_number,
                    "category": category,
                    "club": club,
                    "season": season,
                },
            )
    except IntegrityError:
        # Handle race condition where another process creates the runner
        runner = Runner.objects.get(
            first_name=first_name,
            last_name=last_name,
        )
        # Optionally update details if needed
        runner.participant_number = participant_number
        runner.category = category
        runner.club = club
        runner.save()
        created = False
    return runner, created


class RaceCreateView(LoginRequiredMixin, CreateView):
    model = Race
    template_name = "races/race_form.html"
    form_class = RaceForm

    @transaction.atomic
    def form_valid(self, form):
        race = form.save(commit=False)
        race_count = Race.objects.count()
        race_number = race_count + 1
        race.race_number = race_number

        race.save()
        self.object = race
        season_object = Season.objects.get(season_start_year=race.season_start_year)

        if self.request.FILES:
            excel_file = self.request.FILES["race_file"]
            if isinstance(excel_file, InMemoryUploadedFile):
                df = pd.read_excel(excel_file)
                results = []
                for _, row in df.iterrows():
                    first_name = row["First Name"]
                    last_name = row["Last Name"]
                    participant_number = row["Participant Number"]
                    category = row["Category"]
                    club = row["Club"] if not isnull(row["Club"]) else "Unattached"
                    time_str = row["Time"]

                    if time_str == "DNF":
                        time = "02:00:00"
                        dnf = False
                    else:
                        time = pd.to_timedelta(time_str)
                        dnf = False

                    # Use get_or_create to handle duplicates gracefully
                    runner, created = get_or_create_runner(
                        first_name=first_name,
                        last_name=last_name,
                        participant_number=participant_number,
                        category=category,
                        club=club,
                        season=season_object,
                    )

                    result = Result(race=self.object, runner=runner, time=time, dnf=dnf)
                    results.append(result)

            # Save all results at once
            Result.objects.bulk_create(results)

            # Refresh results from db
            results = list(self.object.result_set.all())
            self.object.calculate_positions()

            # Call create_result_versions with the race's season_start_year
            create_result_versions(
                self.object, season_start_year=race.season_start_year
            )

        return super().form_valid(form)


class RaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Race
    template_name = "races/race_form.html"
    fields = ["name", "description", "race_date", "race_file"]
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def form_valid(self, form):
        if "race_file" in form.changed_data:
            self.object = form.save()

            # Remove old results related to this race
            Result.objects.filter(race=self.object).delete()

            # Get the new data from the file
            data = pd.read_excel(self.object.race_file.path)
            for _, row in data.iterrows():
                first_name, last_name, category, club, time = row
                runner, _ = Runner.objects.get_or_create(
                    first_name=first_name,
                    last_name=last_name,
                    category=category,
                    club=club,
                )
                Result.objects.get_or_create(
                    race=self.object, runner=runner, time=pd.to_timedelta(time)
                )

            self.object.calculate_positions()

            # Call create_result_versions with the race's season_start_year
            create_result_versions(
                self.object, season_start_year=self.object.season_start_year
            )

            return super().form_valid(form)
        else:
            return super().form_valid(form)


class RaceDeleteView(DeleteView):
    model = Race
    template_name = "races/race_confirm_delete.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    success_url = reverse_lazy("races:list")


def custom_404(request, exception):
    return redirect("home")
