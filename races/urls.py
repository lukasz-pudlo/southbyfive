from django.urls import path

from races.views import (
    RaceCreateView,
    RaceDatesView,
    RaceDeleteView,
    RaceDetailView,
    RaceListView,
    RaceUpdateView,
    standings_explain,
)

app_name = "races"

urlpatterns = [
    path("", RaceListView.as_view(), name="list"),
    path("race/new/", RaceCreateView.as_view(), name="new"),
    path("dates/", RaceDatesView.as_view(), name="dates"),
    path("dates/<int:year>/", RaceDatesView.as_view(), name="season_dates"),
    path("<int:year>/race/<slug:slug>/", RaceDetailView.as_view(), name="detail"),
    path(
        "<int:year>/race/<slug:slug>/standings/<int:runner_id>/",
        standings_explain,
        name="standings_explain",
    ),
    path("race/<slug:slug>/edit/", RaceUpdateView.as_view(), name="edit"),
    path("race/<slug:slug>/delete/", RaceDeleteView.as_view(), name="delete"),
    path("<int:season>/", RaceListView.as_view(), name="season_races"),
]
