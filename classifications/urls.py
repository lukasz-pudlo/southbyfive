from django.urls import path
from classifications.views import ClassificationListView, ClassificationDetailView

app_name = 'classifications'

urlpatterns = [
    path('', ClassificationListView.as_view(),
         name='list'),
    path('classification/<slug:slug>/', ClassificationDetailView.as_view(),
         name='detail')
]
