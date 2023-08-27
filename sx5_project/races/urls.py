from django.urls import path
from races.views import RaceListView, RaceDetailView, RaceCreateView, RaceUpdateView, RaceDeleteView, ClassificationListView, ClassificationDetailView

app_name = 'races'

urlpatterns = [
    path('', RaceListView.as_view(), name='list'),
    path('race/<int:pk>/', RaceDetailView.as_view(), name='detail'),
    path('race/new/', RaceCreateView.as_view(), name='new'),
    path('race/<int:pk>/edit/', RaceUpdateView.as_view(), name='edit'),
    path('race/<int:pk>/delete/',
         RaceDeleteView.as_view(), name='delete'),
    path('classifications/', ClassificationListView.as_view(),
         name='classification_list'),
    path('classifications/<int:pk>/', ClassificationDetailView.as_view(),
         name='classification_detail')
]
