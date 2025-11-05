from django.urls import path

from classifications.views import (ClassificationDetailView,
                                   ClassificationListView)

app_name = "classifications"

urlpatterns = [
    path("", ClassificationListView.as_view(), name="list"),
    path(
        "classification/<slug:slug>/", ClassificationDetailView.as_view(), name="detail"
    ),
]
