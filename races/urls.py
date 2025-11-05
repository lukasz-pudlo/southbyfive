from django.urls import path

from races.views import (RaceCreateView, RaceDeleteView, RaceDetailView,
                         RaceListView, RaceUpdateView)

app_name = "races"

urlpatterns = [
    path("", RaceListView.as_view(), name="list"),
    path("race/new/", RaceCreateView.as_view(), name="new"),
    path("<int:year>/race/<slug:slug>/", RaceDetailView.as_view(), name="detail"),
    path("race/<slug:slug>/edit/", RaceUpdateView.as_view(), name="edit"),
    path("race/<slug:slug>/delete/", RaceDeleteView.as_view(), name="delete"),
    path("<int:season>/", RaceListView.as_view(), name="season_races"),
]
