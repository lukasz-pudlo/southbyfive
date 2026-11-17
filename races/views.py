import sys
import traceback

import pandas as pd
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.defaults import server_error
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from classifications.models import ClassificationResult
from races.forms import RaceDatesForm, RaceForm
from races.importing import create_results_for_race, get_or_create_runner  # noqa: F401
from races.models import Race, Season
from races.utils import create_result_versions


def home(request):
    # Retrieve distinct season years for the Seasons dropdown
    season = (
        Race.objects.values_list("season_start_year", flat=True)
        .distinct()
        .order_by("-season_start_year")
        .first()
    )
    last_race = Race.objects.filter(season__season_start_year=season).first()

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
                .order_by("-race_number")
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

        race = get_object_or_404(Race, slug=slug, season_start_year=season_year)

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


class StaffRequiredMixin(UserPassesTestMixin):
    """Staff only: anyone else is sent to log in, or refused if logged in."""

    def test_func(self):
        return self.request.user.is_active and self.request.user.is_staff


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

        season_object = Season.objects.get(season_start_year=race.season_start_year)
        race.season = season_object

        race.save()
        self.object = race

        if self.request.FILES:
            df = pd.read_excel(self.request.FILES["race_file"])
            rows = [
                {
                    "first_name": row["First Name"],
                    "last_name": row["Last Name"],
                    "participant_number": row["Participant Number"],
                    "category": row["Category"],
                    "club": row["Club"],
                    "time": row["Time"],
                }
                for _, row in df.iterrows()
            ]
            create_results_for_race(self.object, season_object, rows)

            self.object.calculate_positions()

            # Call create_result_versions with the race's season_start_year
            create_result_versions(
                self.object, season_start_year=race.season_start_year
            )

        return super().form_valid(form)


class RaceUpdateView(LoginRequiredMixin, UpdateView):
    # Edits the race's details only. Replacing its results goes through the
    # results import, which can be reviewed and reverted.
    model = Race
    template_name = "races/race_form.html"
    fields = ["name", "description", "race_date"]
    slug_field = "slug"
    slug_url_kwarg = "slug"


class RaceDeleteView(StaffRequiredMixin, DeleteView):
    model = Race
    template_name = "races/race_confirm_delete.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    success_url = reverse_lazy("races:list")


class RaceDatesView(StaffRequiredMixin, View):
    """Enter the planned dates of a season's races. They show in the
    navigation for parks whose results are not up yet."""

    template_name = "races/race_dates.html"

    def dispatch(self, request, *args, **kwargs):
        seasons = Season.objects.order_by("-season_start_year")
        year = kwargs.get("year")
        if year is None:
            self.season = seasons.first()
        else:
            self.season = seasons.filter(season_start_year=year).first()
        self.seasons = seasons
        return super().dispatch(request, *args, **kwargs)

    def render(self, request, form):
        published = {}
        if self.season is not None:
            published = {
                race.name: race for race in Race.objects.filter(season=self.season)
            }
        rows = [
            {"field": field, "race": published.get(field.label)} for field in form or []
        ]
        return render(
            request,
            self.template_name,
            {"season": self.season, "seasons": self.seasons, "form": form, "rows": rows},
        )

    def get(self, request, *args, **kwargs):
        if self.season is None:
            if kwargs.get("year") is not None:
                return redirect("races:dates")
            return self.render(request, None)
        return self.render(request, RaceDatesForm(season=self.season))

    def post(self, request, *args, **kwargs):
        if self.season is None:
            return redirect("races:dates")
        form = RaceDatesForm(request.POST, season=self.season)
        if form.is_valid():
            form.save()
            messages.success(request, "Race dates saved.")
            return redirect("races:season_dates", year=self.season.season_start_year)
        return self.render(request, form)


def custom_404(request, exception):
    return redirect("home")


def custom_500(request):
    """Show the error and traceback to staff; everyone else gets the plain 500.

    Django calls this while still handling the exception, so sys.exc_info()
    holds it. The page is rendered without context processors, so it makes no
    database queries and still works when the error came from the database.
    """
    exc_type, exc, tb = sys.exc_info()
    try:
        show_details = exc is not None and request.user.is_staff
    except Exception:
        show_details = False
    if not show_details:
        return server_error(request)

    html = render_to_string(
        "500_staff.html",
        {
            "method": request.method,
            "path": request.path,
            "error_type": exc_type.__name__,
            "error_message": str(exc),
            "traceback": "".join(traceback.format_exception(exc_type, exc, tb)),
        },
    )
    return HttpResponseServerError(html)
