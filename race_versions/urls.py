from django.urls import path

from race_versions.views import RaceVersionDetailView, RaceVersionListView

app_name = "race-versions"

urlpatterns = [
    path("", RaceVersionListView.as_view(), name="race_version_list"),
    path(
        "race-version/<int:pk>/",
        RaceVersionDetailView.as_view(),
        name="race_version_detail",
    ),
]
